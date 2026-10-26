export interface CuratedLearningResource {
  id: string
  title: string
  publisher: string
  category: 'AI 基础' | '产品设计' | '工程实践' | '行业应用'
  format: '课程' | '指南' | '案例库'
  url: string
  description: string
  accent: 'pine' | 'amber' | 'sky' | 'clay'
}

export const curatedLearning: CuratedLearningResource[] = [
  { id: 'google-mlcc', title: 'Machine Learning Crash Course', publisher: 'Google', category: 'AI 基础', format: '课程', url: 'https://developers.google.com/machine-learning/crash-course', description: '用交互练习建立机器学习核心概念，适合非算法岗位补齐共同语言。', accent: 'pine' },
  { id: 'ms-genai', title: 'Generative AI for Beginners', publisher: 'Microsoft', category: 'AI 基础', format: '课程', url: 'https://github.com/microsoft/generative-ai-for-beginners', description: '从概念、提示到应用构建的开放课程。', accent: 'sky' },
  { id: 'openai-cookbook', title: 'OpenAI Cookbook', publisher: 'OpenAI', category: '工程实践', format: '案例库', url: 'https://cookbook.openai.com/', description: '可运行的模型应用示例与工程模式。', accent: 'clay' },
  { id: 'pair-guidebook', title: 'People + AI Guidebook', publisher: 'Google PAIR', category: '产品设计', format: '指南', url: 'https://pair.withgoogle.com/guidebook/', description: '把人机协作、安全边界和反馈机制带进产品决策。', accent: 'amber' },
  { id: 'ms-hax', title: 'Guidelines for Human-AI Interaction', publisher: 'Microsoft Research', category: '产品设计', format: '指南', url: 'https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/', description: '面向 AI 交互设计的实用检查框架。', accent: 'sky' },
  { id: 'uk-ai-playbook', title: 'AI Playbook for the UK Government', publisher: 'UK Government', category: '行业应用', format: '指南', url: 'https://www.gov.uk/government/publications/ai-playbook-for-the-uk-government', description: '从治理、采购到落地，理解公共部门如何采用 AI。', accent: 'pine' },
]
