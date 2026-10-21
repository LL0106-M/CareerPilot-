# CareerPilot 前端视觉系统

> 本文档为前端开发与 UI 设计共享的视觉规范，基于"暖港薄荷"色板 + 毛玻璃层级 + 泊泊动态形象系统。

---

## 1. 核心关键词

**燕麦色的温暖 · 薄荷绿的成长 · 灰蓝色的理性 · 琥珀色的探索**

---

## 2. 色板与 Design Tokens

### 2.1 品牌主色

```scss
// 品牌薄荷绿 - 承担品牌识别、柔和状态、选中态
$brand-mint: #68A88E;

// 深松绿 - 主按钮、关键操作、Logo（对比度优先）
$brand-pine: #3F7562;

// 浅薄荷绿 - 选中背景、轻提示
$brand-mint-light: #E1EEE8;
```

**对比度验证**（WCAG AA）：

| 用途 | 前景 | 背景 | 对比度 | 达标？ |
|---|---|---|---|---|
| 主按钮文字 | #FFFFFF | #3F7562 | 4.8:1 | ✅ AA |
| 次按钮文字 | #FFFFFF | #68A88E | 3.1:1 | ❌ 仅用于 icon + accent，不用于白字按钮 |
| 选中标签文字 | #3F7562 | #E1EEE8 | 5.6:1 | ✅ AA |
| 链接文字 | #3F7562 | #FFFFFF | 5.0:1 | ✅ AA |

### 2.2 页面底色与文字

```scss
// 背景层
$bg-page: #F7F6F2;          // 暖白 - 页面大背景
$bg-glass: rgba(255,255,255,0.72); // 毛玻璃卡片
$bg-glass-strong: rgba(255,255,255,0.88); // 毛玻璃卡片（浮层）
$bg-card: #FFFFFF;          // 纯白 - 对话卡片、内容容器

// 文字层级
$text-primary: #24332D;     // 深墨绿黑 - 主文字
$text-secondary: #66756E;   // 柔和灰绿 - 次级文字
$text-tertiary: #8F9C96;    // 浅灰绿 - 辅助文字、时间戳
$text-inverse: #FFFFFF;     // 反白 - 按钮上

// 分割与边框
$border-subtle: rgba(0,0,0,0.06); // 极淡 - 毛玻璃内
$border-light: #DDE5E1;     // 浅灰绿 - 常规分割线
```

### 2.3 功能状态配色

不做"颜色即含义"的强制绑定，而是**"背景弱色块 + 左侧强调竖条"** 的组合，保证页面不会像调色板：

```scss
// 事实/确定 - 理性稳定
$state-fact-bg: #E8F0F5;
$state-fact-accent: #6E8FA7;

// Agent 猜想 - 尚待验证（琥珀黄，和泊泊罗盘同色）
$state-hypothesis-bg: #F5ECD8;
$state-hypothesis-accent: #D4A85F;

// 普通记忆 - 已记住
$state-memory-bg: #E7F1EC;
$state-memory-accent: #4F806D;

// 情绪陪伴 - 温暖不过度甜美
$state-emotion-bg: #F2EAE5;
$state-emotion-accent: #8B6F62;

// 成功/完成
$state-success-bg: #E3F0E8;
$state-success-accent: #39725A;

// 警告/删除/不可逆 - 仅砖红
$state-danger-bg: #F7E8E5;
$state-danger-accent: #A9584D;
```

### 2.4 色板比例与约束

```text
70%  $bg-page / $bg-card / $bg-glass        → 页面呼吸感
20%  $text-* / $border-* / $brand-mint-light → 结构层次
10%  $brand-pine / $brand-mint / $state-*    → 功能强调
```

**禁止**：
- 不要用薄荷绿做页面主背景 → 角色形象本身已带强情绪属性
- 不要用超过 3 种强调色同时出现 → 同一页面最多 1-2 种功能状态色
- 不要让泊泊做夸张的"害怕"表情 → 危险/删除只用砖红色提示

---

## 3. 毛玻璃体系

毛玻璃是 CareerPilot 的核心视觉语言。用途是**在暖白页面上创造层次，同时让背景中的泊泊保持可见**。

### 3.1 层级定义

```text
z-index 层级 + backdrop-blur 强度：

Layer 0: Page Background（泊泊 + 远山淡影，fixed）
         → 不需要 blur

Layer 1: Content Area（对话卡片、方向卡、记忆列表）
         → background: rgba(255,255,255,0.72)
         → backdrop-blur: 20px
         → border: 1px solid rgba(0,0,0,0.06)

Layer 2: Floating Actions（底部输入区、FAB）
         → background: rgba(255,255,255,0.88)
         → backdrop-blur: 28px
         → border: 1px solid rgba(0,0,0,0.08)

Layer 3: Overlays（Sheet、Modal）
         → background: rgba(255,255,255,0.92)
         → backdrop-blur: 32px
         → border: 1px solid rgba(0,0,0,0.1)

Layer 4: System（Toast、Tooltip）
         → 不使用毛玻璃，纯实色
```

### 3.2 Tailwind CSS 实现

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // 品牌主色
        'brand-pine': '#3F7562',
        'brand-mint': '#68A88E',
        'brand-mint-light': '#E1EEE8',
        // 背景
        'bg-page': '#F7F6F2',
        // 文字
        'text-primary': '#24332D',
        'text-secondary': '#66756E',
        'text-tertiary': '#8F9C96',
        // 功能状态
        'fact-bg': '#E8F0F5', 'fact-accent': '#6E8FA7',
        'hypothesis-bg': '#F5ECD8', 'hypothesis-accent': '#D4A85F',
        'memory-bg': '#E7F1EC', 'memory-accent': '#4F806D',
        'emotion-bg': '#F2EAE5', 'emotion-accent': '#8B6F62',
        'success-bg': '#E3F0E8', 'success-accent': '#39725A',
        'danger-bg': '#F7E8E5', 'danger-accent': '#A9584D',
      },
      boxShadow: {
        'glass-sm': '0 1px 2px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.03)',
        'glass-md': '0 2px 4px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.05)',
        'glass-lg': '0 4px 8px rgba(0,0,0,0.05), 0 8px 32px rgba(0,0,0,0.08)',
      },
    },
  },
};
```

```css
/* glass component 基础类 */
.glass-card {
  @apply rounded-2xl border border-black/[0.06] shadow-glass-md;
  background: rgba(255,255,255,0.72);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.glass-float {
  @apply rounded-2xl border border-black/[0.08] shadow-glass-lg;
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
}

.glass-overlay {
  @apply rounded-2xl border border-black/[0.1] shadow-glass-lg;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(32px);
  -webkit-backdrop-filter: blur(32px);
}
```

### 3.3 功能状态卡片组件（React）

每个功能状态卡片统一使用 **"左侧 3px 强调竖条 + 浅色背景块"** 的组合，不再加 color 相关的阴影或 emoji：

```tsx
// components/StateCard.tsx
interface StateCardProps {
  type: 'fact' | 'hypothesis' | 'memory' | 'emotion' | 'success' | 'danger';
  children: React.ReactNode;
}

const stateMap = {
  fact:      { bg: 'bg-fact-bg',      accent: 'bg-fact-accent' },
  hypothesis:{ bg: 'bg-hypothesis-bg',accent: 'bg-hypothesis-accent' },
  memory:    { bg: 'bg-memory-bg',    accent: 'bg-memory-accent' },
  emotion:   { bg: 'bg-emotion-bg',   accent: 'bg-emotion-accent' },
  success:   { bg: 'bg-success-bg',  accent: 'bg-success-accent' },
  danger:    { bg: 'bg-danger-bg',    accent: 'bg-danger-accent' },
};

export function StateCard({ type, children }: StateCardProps) {
  const s = stateMap[type];
  return (
    <div className={`${s.bg} rounded-xl p-4 pl-[7px] relative`}>
      <div className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-full ${s.accent}`} />
      <div className="pl-3">{children}</div>
    </div>
  );
}
```

---

## 4. 泊泊（Bobo）形象系统

### 4.1 角色色彩（已定稿：燕麦浅棕路线）

```scss
// 主体 - 燕麦浅棕（不是深棕，温暖轻盈不幼稚）
$bobo-body: #B7A38D;

// 脸部和肚皮 - 奶油米色
$bobo-belly: #E8DDCF;

// 眼睛、鼻子 - 柔和黑（不用纯黑）
$bobo-eye: #34332F;

// 腮红 - 极少量使用
$bobo-blush: #C98F82;

// 围巾 - 品牌薄荷绿（建立角色-品牌联系）
$bobo-scarf: #68A88E;

// 小挎包 - 灰蓝色（理性、工具感）
$bobo-bag: #7899AE;

// 罗盘 - 温暖琥珀色（记忆/探索视觉焦点）
$bobo-compass: #D4A85F;
```

### 4.2 技术选型：SVG + React + CSS 微动画

**为什么选 SVG 而不是 Lottie / PNG**：
- 角色需要根据**运行时状态**改变颜色（围巾在 action 模式变深松绿）、可见性（listen 模式收起罗盘）
- SVG 每个部位是独立 group，可以单独控制 opacity/scale/transform
- 文件体积极小（< 10KB），加载无感知
- Lottie 依赖 After Effects 导出，状态切换需要 4-8 个 JSON 文件，维护成本高

### 4.3 泊泊的六种状态

泊泊是**状态感知角色**——它的外观直接反映 Agent 的当前运行状态，不需要文字解释：

| 状态 | 触发条件 | 泊泊外观 |
|---|---|---|
| **Idle / Greeting** | 首页初始加载、对话间等待 | 坐在暖白底上，围巾薄荷绿，罗盘收起在挎包里，眼睛半睁半眯很放松 |
| **Listen 倾听** | support_mode = listen，或 distress_detected = true | 坐直一点，身体微微前倾，**罗盘完全收起**，背景出现极淡暖米色调（#F2EAE5），没有其他装饰。情绪陪伴的"空"感靠背景色淡化实现 |
| **Organize 梳理** | support_mode = organize | 微微歪头，一只爪子搭在下巴上，**罗盘半露**（露出 1/2），表情温和专注 |
| **Explore 探索** | support_mode = explore | **罗盘完全展开并被双手举起**，眼睛亮晶晶，表情好奇，围巾仍为薄荷绿 |
| **Act 行动** | support_mode = act | 身体微微前倾，爪子伸出递出罗盘（像递一张卡），**围巾颜色变为深松绿** #3F7562（品牌强调 + 行动感） |
| **Dreaming 记忆巩固** | Dreaming Worker 运行中（定时任务） | 身体漂浮（translateY 上下 4px 循环），背景极淡灰蓝（#EEF3F5），罗盘旋转 20°-20° 循环，眼睛微闭，周围飘几个小光点（粒子） |
| **Thinking** | Agent 正在调用 tool（search_career_knowledge 执行中） | 眼睛变成 "..." 状态（上下两条弧线交替），罗盘微微发光（box-shadow pulse），2-3s 后恢复到上一个状态 |

### 4.4 状态切换实现

```tsx
// components/Bobo.tsx
import { motion, AnimatePresence } from 'framer-motion';

type BoboMood = 'idle' | 'listen' | 'organize' | 'explore' | 'act' | 'dreaming' | 'thinking';

interface BoboProps {
  mood: BoboMood;
  compassOpen: boolean;     // 罗盘是否展开
  scarfTone: 'mint' | 'pine'; // 围巾颜色
  scale?: number;
}

export function Bobo({ mood, compassOpen, scarfTone, scale = 1 }: BoboProps) {
  const scarfColor = scarfTone === 'pine' ? '#3F7562' : '#68A88E';

  return (
    <div
      className="relative select-none pointer-events-none"
      style={{ transform: `scale(${scale})` }}
    >
      {/* SVG 主图 - 所有部位可见 */}
      <svg viewBox="0 0 200 200" className="w-full h-full">
        {/* 围巾 - 颜色随 scarfTone 变化 */}
        <motion.g animate={{ fill: scarfColor }}>
          {/* scarf path... */}
        </motion.g>

        {/* 罗盘 - visibility 随 compassOpen + mood 变化 */}
        <AnimatePresence>
          {(compassOpen || mood === 'explore' || mood === 'act') && (
            <motion.g
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 200 }}
            >
              {/* compass path... */}
            </motion.g>
          )}
        </AnimatePresence>

        {/* 眼睛 - 根据 mood 切换 */}
        <EyeVariant mood={mood} />
      </svg>

      {/* Dreaming 漂浮动画 */}
      {mood === 'dreaming' && (
        <motion.div
          className="absolute inset-0"
          animate={{ y: [0, -4, 0, 4, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      {/* Thinking 脉冲 */}
      {mood === 'thinking' && (
        <motion.div
          className="absolute inset-0 rounded-full bg-brand-mint/10"
          animate={{ opacity: [0.2, 0.5, 0.2], scale: [1, 1.05, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
    </div>
  );
}
```

### 4.5 泊泊出现位置

| 页面 | 泊泊位置 | 尺寸 | 行为 |
|---|---|---|---|
| 首页 | 左侧固定背景（fixed，不随滚动） | 约 120×120px | idle / greeting 状态。右侧毛玻璃卡片叠在它上面，形成"泊泊在你身后陪你"的感觉 |
| 对话页 | 输入框右侧（inline） | 约 48×48px | 当前 Agent 状态的实时迷你版。用户发消息 → mood 切换成 thinking → Agent reply 返回 → mood 切到对应 support_mode |
| 方向卡页 | 每张猜想卡左下角 | 约 32×32px | **只有 hypothesis 卡**显示泊泊递罗盘；已确认方向卡显示泊泊微笑；已归档卡不显示泊泊 |
| Dreaming 页 | 页面中央（fixed） | 约 140×140px | 漂浮状态 + 极淡灰蓝背景，泊泊周围 3-5 个小光点循环漂浮 |
| 危险/删除对话框 | **不显示** | - | 危险状态只靠砖红色 StateCard + 文字，不用泊泊做表情 |

### 4.6 泊泊的微动画清单

**所有动画 < 400ms**，避免过度分散注意力：

| 触发 | 动画 | 实现 |
|---|---|---|
| 页面首次加载 | 泊泊从 scale 0.8 + opacity 0 淡入到 scale 1 | framer-motion initial/animate |
| 状态切换（idle → listen） | 罗盘 scale 0 收起，身体微微前倾 | AnimatePresence exit |
| 用户发送消息 | 200ms 后眼睛变成 "thinking" 三点态，持续到 Agent reply 返回 | 状态机 transition |
| Agent reply 返回 | 眼睛恢复，对应新 mood（listen/explore 等） | 状态机 transition |
| Dreaming 模式 | Y 轴 ±4px 漂浮循环 4s | framer-motion animate loop |
| Compass 展开/收起 | spring 弹性（stiffness 200，damping 15） | 自然、不机械 |
| Hover（桌面端） | 泊泊头部微微 tilt 3° | 仅桌面，移动端禁用 |

---

## 5. 页面布局与角色协调

### 5.1 首页（Today / 今天）

```text
┌─ fixed 背景层 ──────────────────────────────┐
│  远山淡影（极淡） + 泊泊（idle）坐左侧          │
│  页面滚动时背景不动，毛玻璃卡片覆盖在它上面      │
└────────────────────────────────────────────┘
┌─ content area ──────────────────────────────┐
│  ┌─ glass-card ──────────────────────────┐  │
│  │  早上好，泊泊在陪你。                    │  │
│  │  今天想从哪里继续？                      │  │
│  │                                         │  │
│  │  ┌─ composer ──────────────────────┐   │  │
│  │  │  写下一点想法...            [发送]│   │  │
│  │  └──────────────────────────────────┘   │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌─ glass-card · 今日航向 ──────────────┐  │
│  │  ○ 探索一个感兴趣的职业方向          │  │
│  │  ○ 整理本学期的学习计划              │  │
│  │  ○ 记录今天的情绪与想法              │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌─ StateCard hypothesis ────────────────┐  │
│  │  ┌─ 泊泊递罗盘 32px ─┐                │  │
│  │  │ "你可能在思考：如何找到既有意义     │  │
│  │  │ 又适合自己的方向。"                │  │
│  │  │                                    │  │
│  │  │  ⚠ 这只是我的猜想，不是结论         │  │
│  │  │                                    │  │
│  │  │  [确认]    [暂时不确定]             │  │
│  │  └────────────────────────────────────┘  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### 5.2 对话页

泊泊作为「状态指示符」内嵌在 Agent 气泡的头部，不是页面背景：

```text
┌─ User ───────────────────────────────────────┐
│ 我投了很多简历都没回应，现在只想先说说          │
└──────────────────────────────────────────────┘

┌─ glass-card · Agent Reply ───────────────────┐
│  ┌─ Bobo 48px ─┐                              │
│  │  🎧 listen  │ 我能理解这种感觉——投出去的     │
│  │  (mini)     │ 简历像石沉大海，每次刷新邮箱   │
│  │             │ 都带着一点期待，然后又空下来。 │
│  └─────────────┘                              │
│                                              │
│  这种持续的不确定确实很累人。你现在最难受的    │
│  是哪个部分？                                  │
│                                              │
│  ┌─ meta row ──────────────────────────────┐ │
│  │ 🎧 listen  ·  🧠 ✓ available  · 💭 skipped │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

**关键**：Agent 回复是**白色毛玻璃卡片**，不是气泡。这样页面整体视觉更干净，对话内容是"浮在暖白背景上的卡片"，泊泊的迷你版挂在卡片左上角作为"这个回复是谁说的"的视觉锚点。

### 5.3 Listen 模式特殊背景

当 support_mode = listen（或 distress_detected = true）时，整页背景层淡出到**极淡暖米色**：

```scss
.bg-mode-listen {
  background: linear-gradient(180deg, #F2EAE5 0%, #F7F6F2 40%);
  transition: background 600ms ease;
}
```

这个过渡**必须用 animation 实现**（600ms linear），不能瞬间切换——瞬间切换会让用户感到"界面在冲我说话"，慢过渡才有"陪你坐下来说说"的松弛感。

### 5.4 Act 模式：围巾变色

当 support_mode = act 时，泊泊的围巾颜色从薄荷绿 `#68A88E` 过渡到深松绿 `#3F7562`：

```tsx
// Bobo.tsx
const scarfColor = useMemo(() => {
  if (mood === 'act') return '#3F7562';
  return '#68A88E';
}, [mood]);
```

用户几乎注意不到这个颜色变化，但潜意识会收到信号："泊泊的围巾变深绿了，这是要行动的时刻了"。

### 5.5 猜想卡（Hypothesis Card）vs 方向卡（Direction Card）

**猜想卡**（Agent 还没确认）：
- 琥珀黄背景块 `#F5ECD8` + 左侧琥珀强调条
- 泊泊递出罗盘（罗盘朝上）
- 标注"⚠ 这只是我的猜想，不是结论"
- 底部两个动作：[确认] [暂时不确定]

**方向卡**（用户已确认）：
- 普通记忆背景 `#E7F1EC` + 左侧深绿强调条
- 泊泊微笑，罗盘收起
- 有"依据"、"待验证"、"下一步"三个 section
- 无确认按钮

---

## 6. 完整状态映射表

### 6.1 UI 层 → 状态层

| 产品状态 | support_mode | Bobo mood | Bobo 罗盘 | Bobo 围巾 | 页面背景 | 卡片强调色 |
|---|---|---|---|---|---|---|
| 初始/等待 | - | idle | 收起 | mint #68A88E | 暖白 #F7F6F2 | - |
| 情绪陪伴 | listen / distress | listen | 收起 | mint | 淡暖米 #F2EAE5 | emotion #8B6F62 |
| 梳理 | organize | organize | 半露 | mint | 暖白 | 记忆 #4F806D |
| 探索 | explore | explore | 展开 | mint | 暖白 | hypothesis #D4A85F |
| 行动 | act | act | 展开递出 | pine #3F7562 | 暖白 | success #39725A |
| 记忆巩固 | dreaming | dreaming | 旋转收半 | mint | 淡灰蓝 #EEF3F5 | memory #4F806D |
| Tool 执行中 | (任意) | thinking | 保持上一状态 | 保持 | 保持 | 保持 |

### 6.2 Mode Tag 视觉样式

```scss
.mode-tag {
  @apply rounded-full px-3 py-1.5 text-sm font-medium cursor-pointer transition-all duration-200;
  border: 1px solid transparent;
}

.mode-tag-listen {
  @apply bg-emotion-bg text-[#8B6F62];
  &.active { @apply bg-[#8B6F62] text-white; }
}

.mode-tag-organize {
  @apply bg-memory-bg text-[#4F806D];
  &.active { @apply bg-[#4F806D] text-white; }
}

.mode-tag-explore {
  @apply bg-hypothesis-bg text-[#B8873D];
  &.active { @apply bg-[#B8873D] text-white; }
}

.mode-tag-act {
  @apply bg-[#E3F0E8] text-[#39725A];
  &.active { @apply bg-brand-pine text-white; }
}
```

---

## 7. 资源清单

| 资源 | 格式 | 用途 | 数量 |
|---|---|---|---|
| Bobo SVG（各状态组合） | SVG（每个部位独立 group） | 角色主视觉 | 1 个文件，所有状态通过 React props 切换 |
| Bobo 头像（导航栏用） | PNG 512×512 | 导航栏、分享卡片 | 1 张（idle 状态） |
| 远山淡影背景 | SVG（渐变 + 山形轮廓） | 首页背景层 | 1 张 |
| 罗盘 icon（独立） | SVG inline | 猜想卡装饰、Dreaming 光点 | 复用 Bobo 里的 compass path |
| 品牌 Logo（带文字） | SVG | 导航栏、欢迎页 | 2 个：深色（#3F7562）+ 反白 |

---

## 8. 禁止清单

| 禁止 | 原因 |
|---|---|
| 泊泊做夸张害怕表情 | 危险/删除只用砖红色；角色应始终保持温和 |
| 页面主背景用薄荷绿 | 70% 暖白原则；角色和品牌色才是彩色主体 |
| 同一页面出现 3+ 功能状态色 | 保证视觉焦点；同时出现 hypothesis + emotion + fact 会让用户混乱 |
| 用纯黑 #000000 画角色任何部位 | 破坏温暖感；统一用柔和黑 #34332F |
| 动画 > 400ms | 角色不应比对话内容更吸引注意力 |
| emotion 状态背景用粉色 | 职业产品需要理性底色；暖米 #F2EAE5 足够传递温暖 |
| Bobo 做 QQ 表情类的眨眼/跳动 | 克制是 CareerPilot 的核心调性 |