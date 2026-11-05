import { ArrowClockwise, ArrowSquareOut, ChatsCircle } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'

import { api, type InterviewArchiveResource } from '../../../data/api'

export function InterviewArchivePage() {
  const [items, setItems] = useState<InterviewArchiveResource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshMessage, setRefreshMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setItems((await api.getInterviewArchive()).items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '往年题目更新失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    setRefreshMessage('')
    try {
      const result = await api.refreshInterviewArchive()
      setRefreshMessage(result.saved > 0 ? `新收录 ${result.saved} 条来源` : result.processed > 0 ? '已检查，暂未发现新来源' : '请先从罗盘方向开始航程')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '往年题目更新失败')
      setLoading(false)
    }
  }, [load])

  useEffect(() => { void load() }, [load])

  return (
    <section className="library-dashboard library-dashboard--single interview-library">
      <div className="library-main">
        <div className="library-tools interview-library-tools">
          <div>
            <p className="eyebrow">Interview archive</p>
            <h2>往年题目与面经</h2>
            <p>这是历史经验，不代表未来一定出现；每条材料都保留来源和可信度。</p>
          </div>
          <button type="button" className="secondary-button library-refresh" onClick={() => void refresh()} disabled={loading}>
            <ArrowClockwise aria-hidden="true" /><span>刷新</span>
          </button>
          {refreshMessage && <small>{refreshMessage}</small>}
        </div>

        {loading && <div className="state-panel glass-card">正在检查航程触发的面试资料……</div>}
        {error && <div className="state-panel glass-card error" role="alert">{error}</div>}
        {!loading && !error && items.length === 0 && <div className="state-panel glass-card interview-empty"><ChatsCircle size={32} /><h3>还没有往年题目</h3><p>确认方向并开始航程后，相关面经和历史题目才会进入这里。</p></div>}

        {items.length > 0 && <div className="library-shelf"><div className="shelf-row">{items.map((item) => <article className="resource-book accent-amber" key={item.id}><span>{item.publisher}</span><strong>{item.title}</strong><small>{[item.year, item.round].filter(Boolean).join(' · ') || '时间与轮次未知'}</small><small>{item.trust === 'experience' ? '经验帖 · 待交叉验证' : item.trust === 'official' ? '官方来源' : '来源待核实'}</small><p>{item.excerpt}</p><a href={item.url} target="_blank" rel="noreferrer">查看来源 <ArrowSquareOut /></a></article>)}</div></div>}
      </div>
    </section>
  )
}
