import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CareerPilot local embedding service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    os.environ["CAREERPILOT_LOCAL_EMBEDDING_MODEL"] = args.model
    os.environ["CAREERPILOT_LOCAL_EMBEDDING_DEVICE"] = args.device
    os.environ["CAREERPILOT_LOCAL_EMBEDDING_BATCH_SIZE"] = str(args.batch_size)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    uvicorn.run("careerpilot.embedding_service:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
