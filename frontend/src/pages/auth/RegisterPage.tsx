import { Eye, EyeSlash } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../../auth/AuthProvider'
import './auth.css'

export function RegisterPage() {
  const { register, requestVerificationCode } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [sending, setSending] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (countdown <= 0) return
    const timer = window.setTimeout(() => setCountdown((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [countdown])

  async function sendCode() {
    if (!email) return
    setSending(true); setError('')
    try { const result = await requestVerificationCode(email); setCountdown(result.retry_after_seconds) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '验证码发送失败。') }
    finally { setSending(false) }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError('')
    if (password !== confirmPassword) { setError('两次输入的密码不一致。'); return }
    setSubmitting(true)
    try {
      await register({ username, email, verificationCode, password })
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (reason) { setError(reason instanceof Error ? reason.message : '注册失败，请重试。') }
    finally { setSubmitting(false) }
  }

  return <main className="auth-page"><section className="auth-card auth-card-register glass-strong"><img className="auth-logo" src="/assets/careerpilot-wordmark.png" alt="CareerPilot" /><div className="auth-heading"><p className="eyebrow">Create account</p><h1>创建账户</h1><p>验证邮箱后，再开始你的职业探索。</p></div><form onSubmit={(event) => void submit(event)}><label>用户名<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} required /></label><label>邮箱<div className="code-field"><input aria-label="邮箱" type="email" autoComplete="email" value={email} onChange={(event) => { setEmail(event.target.value); setVerificationCode(''); setCountdown(0) }} required /><button type="button" onClick={() => void sendCode()} disabled={sending || countdown > 0 || !email}>{sending ? '发送中…' : countdown > 0 ? `${countdown} 秒后重发` : '发送验证码'}</button></div></label><label>邮箱验证码<input inputMode="numeric" autoComplete="one-time-code" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))} maxLength={6} required /></label><label>密码<div className="password-field"><input aria-label="密码" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /><button type="button" aria-label={showPassword ? '隐藏密码' : '显示密码'} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeSlash /> : <Eye />}</button></div></label><label>确认密码<input type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={8} required /></label>{error && <p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" type="submit" disabled={submitting}>{submitting ? '正在注册…' : '注册'}</button></form><p className="auth-switch">已经有账户？<Link to="/login">登录</Link></p></section></main>
}
