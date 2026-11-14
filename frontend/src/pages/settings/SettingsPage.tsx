import { useEffect, useState } from 'react'

import { useAuth } from '../../auth/AuthProvider'
import { api, type RelationshipDimension } from '../../data/api'

const preferenceQuestions: Array<{
  dimension: RelationshipDimension['dimension']
  question: string
  options: Array<{ value: string; label: string }>
}> = [
  { dimension:'pace', question:'你卡住时，希望我怎么做？', options:[{value:'listen_first',label:'先听我说'},{value:'action_first',label:'帮我拆下一步'}] },
  { dimension:'challenge', question:'我发现你的判断可能有漏洞时？', options:[{value:'gentle',label:'温和提醒'},{value:'direct',label:'可以直接指出'}] },
  { dimension:'detail', question:'你更喜欢怎样的回答？', options:[{value:'concise',label:'先给简短结论'},{value:'detailed',label:'展开完整分析'}] },
  { dimension:'initiative', question:'未完成的问题要怎样处理？', options:[{value:'wait',label:'等我主动提起'},{value:'proactive',label:'以后适时提醒'}] },
]

export function SettingsPage() {
  const { account } = useAuth()
  const [preferences, setPreferences] = useState<Record<string, string>>({})
  const [preferenceState, setPreferenceState] = useState<'loading' | 'idle' | 'saving' | 'error'>('loading')

  async function loadPreferences() {
    try {
      const profile = await api.getRelationshipProfile()
      setPreferences(Object.fromEntries(profile.dimensions.filter((item) => item.status === 'confirmed').map((item) => [item.dimension, item.value])))
      setPreferenceState('idle')
    } catch {
      setPreferenceState('error')
    }
  }

  useEffect(() => { void loadPreferences() }, [])

  async function selectPreference(dimension: RelationshipDimension['dimension'], value: string) {
    setPreferenceState('saving')
    try {
      await api.updateRelationshipPreference(dimension, value)
      setPreferences((current) => ({ ...current, [dimension]: value }))
      setPreferenceState('idle')
    } catch {
      setPreferenceState('error')
    }
  }

  async function resetPreferences() {
    setPreferenceState('saving')
    try {
      await api.resetRelationshipProfile()
      await loadPreferences()
    } catch {
      setPreferenceState('error')
    }
  }

  return (
    <div className="settings-layout">
      <section className="glass-card settings-header">
        <p className="eyebrow">设置</p>
        <h1 className="page-title">泊泊的工作方式由你定</h1>
        <p className="muted">查看账户信息，也可以按自己的习惯调整泊泊的工作方式。</p>
      </section>

      <div className="settings-grid">
        <SettingsCard title="你的账户" description="该账户用于隔离并保护你的个人数据">
          <Row label="用户名" value={account?.username ?? '—'} />
          <Row label="已验证邮箱" value={account?.email ?? '—'} />
        </SettingsCard>

        <SettingsCard title="泊泊的沟通方式" description="不是人格测试，只决定我们怎样更舒服地一起工作">
          <div className="relationship-preferences">
            {preferenceQuestions.map((item) => <div className="preference-question" key={item.dimension}><span>{item.question}</span><div>{item.options.map((option) => <button type="button" key={option.value} className={`preference-option${preferences[item.dimension] === option.value ? ' selected' : ''}`} aria-pressed={preferences[item.dimension] === option.value} disabled={preferenceState === 'saving'} onClick={() => void selectPreference(item.dimension, option.value)}>{option.label}</button>)}</div></div>)}
            <div className="preference-footer"><small>{preferenceState === 'loading' ? '正在读取…' : preferenceState === 'saving' ? '正在保存…' : preferenceState === 'error' ? '暂时没有保存成功。' : '随时可以修改。情绪明显低落时，泊泊仍会临时降低挑战强度。'}</small><button type="button" className="text-button" onClick={() => void resetPreferences()} disabled={preferenceState === 'saving'}>恢复默认</button></div>
          </div>
        </SettingsCard>

        <SettingsCard title="通知强度" description="今天页和桌面通知会用到">
          <Row label="每日问候" value="开启" />
          <Row label="截止岗位提醒" value="提前 3 天" />
          <Row label="离线反思摘要" value="每天早上" />
        </SettingsCard>

        <SettingsCard title="记忆与资料权限" description="这些是将来最需要注意的开关">
          <Row label="允许泊泊读取长期记忆" value="开启" />
          <Row label="允许泊泊写入长期记忆" value="仅保守写入" />
          <Row label="个人资料参与检索" value="开启" />
        </SettingsCard>

        <SettingsCard title="数据" description="随时拿走，随时清空">
          <Row label="导出全部对话和记忆" action="导出 JSON" />
          <Row label="清空长期记忆" action="清空" danger />
          <Row label="删除全部个人资料" action="删除" danger />
        </SettingsCard>
      </div>
    </div>
  )
}

function SettingsCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <section className="glass-card settings-card">
      <h2 className="card-title">{title}</h2>
      <p className="muted settings-card-desc">{description}</p>
      <div className="settings-rows">{children}</div>
    </section>
  )
}

function Row({
  label,
  value,
  action,
  danger,
}: {
  label: string
  value?: string
  action?: string
  danger?: boolean
}) {
  return (
    <div className="settings-row">
      <span>{label}</span>
      {value && <span className="muted">{value}</span>}
      {action && (
        <button
          type="button"
          className={`text-button${danger ? ' danger' : ''}`}
        >
          {action}
        </button>
      )}
    </div>
  )
}
