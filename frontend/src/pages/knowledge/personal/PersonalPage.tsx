import { useState } from 'react'
import { demoDocuments } from '../../../data/demoRepository'
import type { PersonalDocument } from '../../../data/types'

type DocCategory = PersonalDocument['category']

const CATEGORIES: DocCategory[] = ['简历', '项目与作品集', '其他资料']

export function PersonalPage() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [documents, setDocuments] = useState<PersonalDocument[]>(demoDocuments)
  const [activeCategory, setActiveCategory] = useState<DocCategory | '全部'>('全部')

  const visible =
    activeCategory === '全部'
      ? documents
      : documents.filter((d) => d.category === activeCategory)

  return (
    <section className="glass-strong personal-page">
      <div className="personal-header">
        <div>
          <p className="eyebrow">知识库 · 个人资料库</p>
          <h1 className="page-title">个人资料库</h1>
          <p className="muted">
            你的文件只用于授权的检索，不会自动写入长期记忆。
          </p>
        </div>
        <button
          type="button"
          className="primary-button"
          onClick={() => setUploadOpen(true)}
        >
          上传个人资料
        </button>
      </div>

      <div className="personal-categories">
        {(['全部', ...CATEGORIES] as const).map((c) => (
          <button
            key={c}
            type="button"
            className={`category-pill${activeCategory === c ? ' active' : ''}`}
            onClick={() => setActiveCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>

      <table className="docs-table">
        <thead>
          <tr>
            <th>文件名称</th>
            <th>分类</th>
            <th>格式</th>
            <th>大小</th>
            <th>上传时间</th>
            <th>解析状态</th>
            <th>检索</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.title}</td>
              <td><span className="tag">{doc.category}</span></td>
              <td>{doc.format}</td>
              <td>{doc.size}</td>
              <td>{doc.uploadedAt}</td>
              <td><span className={`status status-${doc.status}`}>{doc.status}</span></td>
              <td>
                <span className={doc.retrievalEnabled ? 'status-enabled' : 'status-disabled'}>
                  {doc.retrievalEnabled ? '已启用' : '已停用'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {uploadOpen && (
        <UploadModal
          onClose={() => setUploadOpen(false)}
          onUpload={(doc) => {
            setDocuments((prev) => [doc, ...prev])
            setUploadOpen(false)
          }}
        />
      )}
    </section>
  )
}

function UploadModal({
  onClose,
  onUpload,
}: {
  onClose: () => void
  onUpload: (doc: PersonalDocument) => void
}) {
  const [category, setCategory] = useState<DocCategory>('简历')
  const [title, setTitle] = useState('')

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="glass-card modal-panel">
        <h2 className="card-title">上传个人资料</h2>
        <label className="modal-field">
          <span>资料类型</span>
          <select value={category} onChange={(e) => setCategory(e.target.value as DocCategory)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="modal-field">
          <span>资料名称（选填）</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="留空则使用文件名"
          />
        </label>
        <p className="muted modal-hint">MVP 支持 PDF、DOCX、TXT。</p>
        <div className="modal-actions">
          <button type="button" className="text-button" onClick={onClose}>取消</button>
          <button
            type="button"
            className="primary-button"
            onClick={() =>
              onUpload({
                id: `doc-${Date.now()}`,
                title: title || '新文件',
                category,
                format: 'PDF',
                size: '—',
                uploadedAt: '刚刚',
                status: '解析中',
                retrievalEnabled: false,
              })
            }
          >
            上传
          </button>
        </div>
      </div>
    </div>
  )
}
