import { FileArrowUp, FileText, MagnifyingGlass, Trash } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'

import { api, mapApiDocument } from '../../../data/api'
import type { PersonalDocument } from '../../../data/types'

export function PersonalPage() {
  const [documents,setDocuments] = useState<PersonalDocument[]>([])
  const [query,setQuery] = useState('')
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [selected,setSelected] = useState('')
  const [uploading,setUploading] = useState(false)
  useEffect(() => { api.getDocuments().then(({items}) => setDocuments(items.map(mapApiDocument))).catch((reason) => setError(reason instanceof Error ? reason.message : '加载失败')).finally(() => setLoading(false)) },[])
  const visible = useMemo(() => documents.filter((doc) => doc.title.toLowerCase().includes(query.toLowerCase())),[documents,query])
  const featured = visible.find((doc) => doc.id === selected) || visible[0]
  async function remove(id:string) { if (!window.confirm('确认从个人资料库移除这个文件？')) return; await api.deleteDocument(id); setDocuments((old) => old.filter((doc) => doc.id !== id)) }
  async function upload(file:File) { setUploading(true); setError(''); try { const uploaded = mapApiDocument(await api.uploadDocument(file,'其他资料')); setDocuments((old) => [uploaded,...old]); setSelected(uploaded.id) } catch (reason) { setError(reason instanceof Error ? reason.message : '上传失败') } finally { setUploading(false) } }
  return <section className="library-dashboard personal-library"><aside className="library-rail glass-card"><div className="rail-title"><FileText />最近上传</div>{documents.slice(0,5).map((doc) => <button type="button" key={doc.id} className={featured?.id === doc.id ? 'active' : ''} onClick={() => setSelected(doc.id)}><span>{doc.format.slice(0,1)}</span><div><strong>{doc.title}</strong><small>{doc.category}</small></div></button>)}</aside><div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索个人资料" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索简历、作品集或其他资料" /></label><label className="upload-trigger"><FileArrowUp />{uploading ? '上传中…' : '选择文件'}<input type="file" accept=".pdf,.docx,.txt,.md" disabled={uploading} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file) }} /></label></div>{loading && <div className="library-feature glass-card loading">正在读取你的资料……</div>}{error && <div className="library-feature glass-card error">{error}</div>}{!loading && !error && !featured && <div className="library-feature glass-card empty"><FileArrowUp size={42} /><h2>你的资料，只在你需要时出现</h2><p>这里不会摆放示例简历。上传后文件会先进入解析状态，再开放给对话检索。</p></div>}{featured && <article className="library-feature document-feature"><FileText size={64} weight="thin" /><div><span>{featured.category} · {featured.format}</span><h2>{featured.title}</h2><p>{featured.size} · {featured.uploadedAt} · {featured.status}</p><small>{featured.retrievalEnabled ? '已允许在对话检索中使用' : '尚未进入检索'}</small></div><button type="button" aria-label={`删除 ${featured.title}`} onClick={() => void remove(featured.id)}><Trash /></button></article>}<div className="library-shelf"><header><div><p className="eyebrow">Your materials</p><h2>全部资料</h2></div><span>{visible.length} 个文件</span></header><div className="document-grid">{visible.map((doc) => <button type="button" className="document-tile glass-card" key={doc.id} onClick={() => setSelected(doc.id)}><FileText size={28} /><strong>{doc.title}</strong><span>{doc.category} · {doc.status}</span></button>)}</div></div></div></section>
}
