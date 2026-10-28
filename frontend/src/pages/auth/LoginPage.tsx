import { Eye, EyeSlash } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../auth/AuthProvider'
import './auth.css'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const justRegistered = Boolean((location.state as { registered?: boolean } | null)?.registered)

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setSubmitting(true); setError('')
    try {
      await login(identifier, password, rememberMe)
      const from = (location.state as { from?: string } | null)?.from || '/'
      navigate(from, { replace: true })
    } catch (reason) {
      setPassword('')
      setError(reason instanceof Error ? reason.message : '登录失败，请重试。')
    } finally { setSubmitting(false) }
  }

  return <main className="auth-page"><section className="auth-card glass-strong"><img className="auth-logo" src="/assets/careerpilot-wordmark.png" alt="CareerPilot" /><div className="auth-heading"><p className="eyebrow">Welcome back</p><h1>欢迎回来</h1><p>继续和泊泊一起，慢慢把方向想清楚。</p></div>{justRegistered && <p className="auth-success" role="status">注册成功，请使用新账户登录。</p>}<form onSubmit={(event) => void submit(event)}><label>用户名或邮箱<input autoComplete="username" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required /></label><label>密码<div className="password-field"><input aria-label="密码" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? '隐藏密码' : '显示密码'} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeSlash /> : <Eye />}</button></div></label><label className="remember-row"><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />记住我（5 天内免登录）</label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" type="submit" disabled={submitting}>{submitting ? '正在登录…' : '登录'}</button></form><p className="auth-switch">还没有账户？<Link to="/register">注册</Link></p></section></main>
}
