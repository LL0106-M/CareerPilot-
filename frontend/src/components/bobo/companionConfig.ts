import type { BoboMood } from './Bobo'

export interface CompanionConfig {
  pageKey: string
  label: string
  mood: BoboMood
  prompt: string
  greeting: string
  accent: 'home' | 'compass' | 'journey' | 'knowledge' | 'dreaming' | 'quiet'
  hidden?: boolean
}

const configs: Array<{ match: (pathname: string) => boolean; value: CompanionConfig }> = [
  {
    match: (pathname) => pathname === '/chat',
    value: { pageKey: 'chat', label: '完整对话', mood: 'listen', prompt: '', greeting: '', accent: 'quiet', hidden: true },
  },
  {
    match: (pathname) => pathname.startsWith('/compass'),
    value: {
      pageKey: 'compass', label: '罗盘', mood: 'explore', accent: 'compass',
      prompt: '一起看看这个方向还缺什么。',
      greeting: '你不需要立刻做选择。我们可以先找到最值得验证的一个问题。',
    },
  },
  {
    match: (pathname) => pathname.startsWith('/journey'),
    value: {
      pageKey: 'journey', label: '航程', mood: 'act', accent: 'journey',
      prompt: '现在只推进下一步。',
      greeting: '我会陪你把行动做小一点，也会记得完成之后一起复盘。',
    },
  },
  {
    match: (pathname) => pathname.startsWith('/knowledge'),
    value: {
      pageKey: 'knowledge', label: '知识库', mood: 'organize', accent: 'knowledge',
      prompt: '我可以帮你把资料和方向连起来。',
      greeting: '你可以问这份资料意味着什么，或者它和某个方向有什么关系。',
    },
  },
  {
    match: (pathname) => pathname.startsWith('/dreaming'),
    value: {
      pageKey: 'dreaming', label: 'Dreaming', mood: 'dreaming', accent: 'dreaming',
      prompt: '最近的线索正在慢慢连接。',
      greeting: '这些只是可以被推翻的观察。哪一条让你最有感觉？',
    },
  },
  {
    match: (pathname) => pathname.startsWith('/memory'),
    value: {
      pageKey: 'memory', label: '记忆', mood: 'organize', accent: 'quiet',
      prompt: '记住什么、暂停什么，都由你决定。',
      greeting: '这里的长期记忆可以被确认、修改、暂停或删除。',
    },
  },
  {
    match: (pathname) => pathname.startsWith('/settings'),
    value: {
      pageKey: 'settings', label: '设置', mood: 'idle', accent: 'quiet',
      prompt: '泊泊怎样工作，由你来定。',
      greeting: '如果某种陪伴方式让你不舒服，可以随时告诉我。',
    },
  },
]

const home: CompanionConfig = {
  pageKey: 'home', label: '首页', mood: 'idle', accent: 'home',
  prompt: '从一件小事开始就好。',
  greeting: '我在。你可以说说刚才想到的事，也可以什么都不急着解决。',
}

export function getCompanionConfig(pathname: string): CompanionConfig {
  return configs.find((entry) => entry.match(pathname))?.value ?? home
}
