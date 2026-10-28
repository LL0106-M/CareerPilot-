import { useAuth } from '../../auth/AuthProvider'

export function SettingsPage() {
  const { account } = useAuth()

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

        <SettingsCard title="泊泊的沟通方式" description="默认由泊泊判断当前适合倾听、梳理、探索还是行动">
          <Row label="默认支持模式" value="让泊泊判断" />
          <Row label="语速 / 篇幅" value="简洁" />
          <Row label="外部行动是否需要二次确认" value="始终需要" />
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
