import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from langchain_core.tools import BaseTool

from careerpilot.agent.base import AgentResponder
from careerpilot.agent.orchestration import AgentPlan, AgentStage, AgentVerifier
from careerpilot.agent.prompt import PromptComposer
from careerpilot.context.contracts import RetrievalSource, TaskIntent
from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.harness.memory import MemoryLifecycle
from careerpilot.harness.run_store import SqliteAgentRunStore
from careerpilot.harness.runtime import RunCancellationRequested
from careerpilot.memory.base import MemoryStore
from careerpilot.memory.dreaming import (
    CognitiveStore,
    DreamingTriggerPolicy,
)
from careerpilot.memory.service import MemoryService
from careerpilot.memory.write_policy import MemoryWritePolicy
from careerpilot.support.policy import SupportMode, SupportPolicy


@dataclass(frozen=True, slots=True)
class ChatCommand:
    user_id: str
    conversation_id: str
    message: str
    requested_mode: SupportMode | None = None
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: str
    run_id: str
    result_status: str
    citation_ids: tuple[str, ...]
    citation_warnings: tuple[str, ...]
    reply: str
    support_mode: SupportMode
    primary_intent: TaskIntent
    retrieval_sources: tuple[RetrievalSource, ...]
    memory_read_status: str
    memory_write_status: str
    dreaming_status: str
    memory_ids: tuple[str, ...] = ()


class AgentService:
    def __init__(
        self,
        memory_store: MemoryStore,
        agent: AgentResponder,
        support_policy: SupportPolicy,
        prompt_composer: PromptComposer | None = None,
        memory_write_policy: MemoryWritePolicy | None = None,
        rag_tool_factory: Callable[[str], BaseTool] | None = None,
        action_tool_factory: Callable[[str], tuple[BaseTool, ...]] | None = None,
        cognitive_store: CognitiveStore | None = None,
        dreaming_trigger_policy: DreamingTriggerPolicy | None = None,
        unified_memory_service: MemoryService | None = None,
        run_store: SqliteAgentRunStore | None = None,
        verifier: AgentVerifier | None = None,
    ) -> None:
        self._agent = agent
        self._rag_tool_factory = rag_tool_factory
        self._action_tool_factory = action_tool_factory
        self._run_store = run_store
        self._verifier = verifier or AgentVerifier()
        self._context_compiler = CareerContextCompiler(
            memory_store,
            support_policy,
            prompt_composer or PromptComposer(),
            cognitive_store,
            unified_memory_service=unified_memory_service,
        )
        self._memory_lifecycle = MemoryLifecycle(
            memory_store,
            memory_write_policy or MemoryWritePolicy(),
            cognitive_store,
            dreaming_trigger_policy or DreamingTriggerPolicy(),
            unified_memory_service=unified_memory_service,
        )

    async def chat(self, command: ChatCommand) -> ChatResult:
        run_id = command.run_id or str(uuid4())
        session_id = _scoped_session_id(command.user_id, command.conversation_id)
        if self._run_store is not None:
            await self._run_store.create(
                run_id=run_id,
                owner_id=command.user_id,
                conversation_id=command.conversation_id,
                session_id=session_id,
                objective=command.message,
            )
        try:
            await self._transition(run_id, AgentStage.UNDERSTAND)
            context = await self._context_compiler.compile(
                ContextRequest(
                    user_id=command.user_id,
                    conversation_id=command.conversation_id,
                    message=command.message,
                    requested_mode=command.requested_mode,
                )
            )
            plan = AgentPlan.from_context(
                command.message, context.intent.primary_intent, context.retrieval_plan
            )
            await self._transition(run_id, AgentStage.PLAN, plan.as_dict())
            allowed_tool_names = set(context.allowed_tool_names)
            runtime_tools: list[BaseTool] = []
            if (
                "search_career_knowledge" in allowed_tool_names
                and self._rag_tool_factory is not None
            ):
                runtime_tools.append(self._rag_tool_factory(command.user_id))
            if (
                context.decision.action_tools_allowed
                and self._action_tool_factory is not None
            ):
                action_tools = self._action_tool_factory(command.user_id)
                runtime_tools.extend(action_tools)
                allowed_tool_names.update(tool.name for tool in action_tools)
            await self._raise_if_cancelled(run_id)
            await self._transition(run_id, AgentStage.EXECUTE)
            agent_response = await self._agent.respond(
                command.message,
                context.system_prompt,
                session_id,
                allowed_tool_names=frozenset(allowed_tool_names),
                runtime_tools=tuple(runtime_tools),
                run_id=run_id,
            )
            verification = self._verifier.verify(agent_response, plan)
            await self._transition(
                run_id,
                AgentStage.VERIFY,
                {"verification": verification.as_dict()},
            )
            await self._transition(run_id, AgentStage.LEARN)
            memory_result = await self._memory_lifecycle.commit_turn(
                user_id=command.user_id,
                conversation_id=command.conversation_id,
                user_message=command.message,
                assistant_message=agent_response.reply,
                memories=context.memories,
                turn_id=run_id,
            )
            result = ChatResult(
                conversation_id=command.conversation_id,
                run_id=run_id,
                result_status=verification.status,
                reply=agent_response.reply,
                citation_ids=agent_response.citation_ids,
                citation_warnings=agent_response.citation_warnings,
                support_mode=context.decision.mode,
                primary_intent=context.intent.primary_intent,
                retrieval_sources=tuple(
                    route.source for route in context.retrieval_plan.routes
                ),
                memory_read_status=context.memory_read_status,
                memory_write_status=memory_result.write_status,
                dreaming_status=memory_result.consolidation_status,
                memory_ids=memory_result.memory_ids,
            )
            if self._run_store is not None:
                await self._run_store.complete(
                    run_id,
                    {
                        "result_status": result.result_status,
                        "citation_ids": list(result.citation_ids),
                        "citation_warnings": list(result.citation_warnings),
                        "memory_ids": list(result.memory_ids),
                        "verification": verification.as_dict(),
                    },
                )
            return result
        except RunCancellationRequested:
            await self._transition(run_id, AgentStage.CANCELLED)
            raise
        except Exception as exc:
            if self._run_store is not None:
                await self._run_store.fail(run_id, exc)
            raise

    async def _transition(
        self,
        run_id: str,
        stage: AgentStage,
        data: dict[str, object] | None = None,
    ) -> None:
        if self._run_store is not None:
            await self._run_store.transition_stage(run_id, stage, data=data)

    async def _raise_if_cancelled(self, run_id: str) -> None:
        if self._run_store is not None and await self._run_store.cancellation_requested(
            run_id
        ):
            raise RunCancellationRequested("Agent run cancellation was requested")


def _scoped_session_id(owner_id: str, conversation_id: str) -> str:
    """Create an opaque, collision-resistant session key scoped to one owner."""

    payload = f"{len(owner_id)}:{owner_id}{len(conversation_id)}:{conversation_id}"
    return f"session:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
