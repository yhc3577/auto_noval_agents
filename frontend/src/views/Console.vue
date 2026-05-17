<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ novelTitle }} - 创作控制台</h1>
      <div class="header-actions">
        <el-button
          v-if="progress.status !== 'writing'"
          type="primary"
          :icon="VideoPlay"
          size="large"
          :loading="loading"
          @click="handleStart"
        >
          开始创作
        </el-button>
        <template v-else>
          <el-button
            type="danger"
            :icon="SwitchButton"
            size="large"
            :loading="loading"
            @click="handlePause"
          >
            停止创作
          </el-button>
        </template>
      </div>
    </div>

    <div class="console-layout">
      <!-- 左侧主面板 -->
      <div class="console-main">
        <!-- 进度总览 -->
        <div class="section-card progress-card">
          <div class="progress-header">
            <div>
              <div class="progress-title">创作进度</div>
              <div class="progress-sub">
                <el-tag :type="statusType" effect="light" size="small">{{ statusText }}</el-tag>
                <span v-if="progress.chapter_status" class="chapter-status">
                  {{ chapterStatusText }}
                </span>
              </div>
            </div>
            <div class="progress-pct">{{ Math.round(progress.progress) }}%</div>
          </div>
          <el-progress
            :percentage="Math.round(progress.progress)"
            :stroke-width="12"
            :color="progressColor"
          />
          <div class="progress-stats">
            <div class="stat">
              <span class="stat-label">当前章节</span>
              <span class="stat-value">{{ progress.current_chapter }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">总章节数</span>
              <span class="stat-value">{{ progress.total_chapters }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">剩余章节</span>
              <span class="stat-value">{{ Math.max(0, progress.total_chapters - progress.current_chapter) }}</span>
            </div>
          </div>
        </div>

        <!-- 6Agent 状态 -->
        <div class="section-card">
          <div class="section-title">6Agent 流水线状态</div>
          <div class="agent-pipeline">
            <div
              v-for="agent in agents"
              :key="agent.key"
              class="agent-node"
              :class="{ active: isActive(agent.key), done: isDone(agent.key) }"
            >
              <div class="agent-icon">
                <el-icon :size="20"><component :is="agent.icon" /></el-icon>
              </div>
              <span class="agent-name">{{ agent.name }}</span>
              <span class="agent-status-dot" />
            </div>
          </div>
        </div>

        <!-- 流式创作内容 -->
        <div class="section-card streaming-card" v-if="streamingActive">
          <div class="section-title">
            章节创作实时预览
            <el-tag size="small" type="warning" effect="light" class="streaming-tag">
              <span class="streaming-dot"></span> 实时生成中
            </el-tag>
          </div>
          <div class="streaming-content" ref="streamingRef">
            {{ streamingText }}<span class="cursor-blink">|</span>
          </div>
        </div>

        <!-- 实时日志 -->
        <div class="section-card">
          <div class="section-title">
            实时日志
            <el-button text size="small" @click="clearLog" style="margin-left: auto">清空</el-button>
          </div>
          <div class="log-terminal" ref="logRef">
            <div v-if="logs.length === 0" class="log-empty">等待创作启动...</div>
            <div v-for="(log, i) in logs" :key="i" class="log-line">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-msg">{{ log.msg }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="console-sidebar">
        <!-- 章节列表 -->
        <div class="section-card">
          <div class="section-title">章节列表</div>
          <div class="chapter-list">
            <div
              v-for="ch in chapters"
              :key="ch.chapter_number"
              class="chapter-item"
              :class="{ active: ch.chapter_number === progress.current_chapter }"
              @click="goChapter(ch)"
            >
              <span class="ch-title">{{ formatChapterTitle(ch.chapter_number, ch.title) }}</span>
              <el-tag :type="ch.status === 'completed' ? 'success' : 'info'" size="small" effect="plain">
                {{ ch.status === 'completed' ? '完成' : ch.status }}
              </el-tag>
            </div>
            <el-empty v-if="chapters.length === 0" description="暂无章节" :image-size="48" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCreationStore } from '@/stores/creation'
import { useNovelStore } from '@/stores/novel'
import api from '@/services/api'
import { ElMessage } from 'element-plus'
import {
  VideoPlay, SwitchButton, EditPen, Memo, Reading,
  Operation
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const creationStore = useCreationStore()
const novelStore = useNovelStore()
const loading = ref(false)
const logRef = ref<HTMLElement>()
const chapters = ref<any[]>([])
const novelTitle = ref('')

const projectId = route.params.id as string

// 设置当前活跃项目
creationStore.setActiveProject(projectId)
const progress = computed(() => creationStore.progress)
const logs = ref<{ time: string; msg: string }[]>([])
const streamingRef = ref<HTMLElement>()
const streamingText = computed(() => creationStore.streamingContent[projectId] || '')
const streamingActive = computed(() => creationStore.streamingActive[projectId] || false)

const agents = [
  { key: 'dispatch', name: '调度', icon: Operation },
  { key: 'writing', name: '写作', icon: EditPen },
  { key: 'summarizing', name: '摘要', icon: Memo },
  { key: 'auditing', name: '审核', icon: Reading },
  { key: 'copyright', name: '版权', icon: Memo },
]

const agentOrder = ['dispatch', 'writing', 'summarizing', 'auditing', 'copyright_checking']
const chapterStatusMap: Record<string, string> = {
  writing: '写作中', summarizing: '生成摘要', auditing: '剧情审核',
  copyright_checking: '版权校验', completed: '已完成', rewriting: '重写中',
}

const statusType = computed(() => {
  const map: Record<string, string> = { idle: 'info', writing: 'warning', paused: 'info', completed: 'success' }
  return (map[progress.value.status] || 'info') as any
})

const statusText = computed(() => {
  const map: Record<string, string> = { idle: '待启动', writing: '创作中', paused: '已暂停', completed: '已完成' }
  return map[progress.value.status] || progress.value.status
})

const chapterStatusText = computed(() => chapterStatusMap[progress.value.chapter_status] || progress.value.chapter_status)

const progressColor = computed(() =>
  progress.value.status === 'completed' ? 'var(--color-success)' : 'var(--color-primary)'
)

function isActive(key: string) {
  return progress.value.status === 'writing' && progress.value.chapter_status === key
}

function isDone(key: string) {
  if (progress.value.status !== 'writing') return false
  const idx = agentOrder.indexOf(progress.value.chapter_status)
  const keyIdx = agents.findIndex(a => a.key === key)
  return idx > keyIdx || progress.value.chapter_status === 'completed'
}

function addLog(msg: string) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  logs.value.push({ time, msg })
  if (logs.value.length > 200) logs.value.shift()
  nextTick(() => {
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

function clearLog() { logs.value = [] }

const chineseNums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

function toChineseNum(num: number): string {
  if (num <= 10) return chineseNums[num]
  if (num < 20) return '十' + chineseNums[num - 10]
  if (num < 100) {
    const tens = Math.floor(num / 10)
    const ones = num % 10
    return chineseNums[tens] + '十' + (ones ? chineseNums[ones] : '')
  }
  return String(num)
}

function formatChapterTitle(chapterNumber: number, title: string): string {
  // 如果标题已经包含"第X章"前缀，直接返回
  if (/^第[一二三四五六七八九十百千\d]+章/.test(title)) {
    return title
  }
  // 否则添加"第X章："前缀
  const prefix = `第${toChineseNum(chapterNumber)}章`
  return title ? `${prefix}：${title}` : prefix
}

async function loadChapters() {
  try {
    const { data } = await api.get('/chapter/list', { params: { project_id: projectId, page_size: 100 } })
    chapters.value = data.items || []
  } catch {}
}

function goChapter(ch: any) {
  router.push(`/novel/${projectId}/chapter/${ch.chapter_id}`)
}

async function handleStart() {
  loading.value = true
  try {
    await creationStore.startCreation(projectId)
    addLog('创作流水线已启动')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
  } finally { loading.value = false }
}

async function handlePause() {
  loading.value = true
  try {
    await creationStore.pauseCreation(projectId)
    addLog('创作已暂停')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '暂停失败')
  } finally { loading.value = false }
}

watch(() => progress.value.log, (newLog) => {
  if (newLog) addLog(newLog)
})

watch(() => progress.value.current_chapter, () => {
  loadChapters()
})

watch(() => progress.value.chapter_status, (newStatus, oldStatus) => {
  if (newStatus === 'writing' && oldStatus !== 'writing') {
    creationStore.subscribeStreamContent(projectId)
  }
})

watch(streamingText, () => {
  nextTick(() => {
    if (streamingRef.value) {
      streamingRef.value.scrollTop = streamingRef.value.scrollHeight
    }
  })
})

onMounted(async () => {
  creationStore.setActiveProject(projectId)

  // 先加载章节列表，获取真实章节数
  await loadChapters()

  // 从后端获取项目真实状态，同步进度到本地store（实时查询，不使用缓存）
  try {
    const detail = await novelStore.fetchNovelDetail(projectId)
    if (detail) {
      novelTitle.value = detail.title || ''
      creationStore.progressMap[projectId] = {
        ...creationStore.progressMap[projectId],
        current_chapter: detail.current_chapter ?? 0,
        total_chapters: detail.chapter_count ?? 0,
        status: detail.status ?? 'idle',
      }
      // 如果后端显示不在创作中，且之前 state 为 writing，说明状态已过期
      if (detail.status !== 'writing' && creationStore.progressMap[projectId]?.status === 'writing') {
        creationStore.progressMap[projectId].status = detail.status
      }
    }
  } catch (e) {
    console.error('获取项目状态失败:', e)
  }

  // 如果没有章节，确保进度归零
  if (chapters.value.length === 0) {
    creationStore.progressMap[projectId] = {
      ...creationStore.progressMap[projectId],
      current_chapter: 0,
    }
  }

  if (progress.value.log) addLog(progress.value.log)

  // 如果正在创作中，自动订阅 SSE 进度流
  if (progress.value.status === 'writing') {
    creationStore.subscribeProgress(projectId)
  }

  // 如果正在写作中，订阅流式内容
  if (progress.value.chapter_status === 'writing') {
    creationStore.subscribeStreamContent(projectId)
  }
})

onUnmounted(() => {
  creationStore.unsubscribeProgress(projectId)
  creationStore.unsubscribeStreamContent(projectId)
})
</script>

<style scoped>
.console-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--space-lg);
  align-items: start;
}

.header-actions {
  display: flex;
  gap: var(--space-sm);
}

/* ── 进度卡片 ── */
.progress-card {
  padding: var(--space-xl);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-md);
}

.progress-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.progress-sub {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-xs);
}

.chapter-status {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.progress-pct {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1;
}

.progress-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md);
  margin-top: var(--space-lg);
  padding-top: var(--space-lg);
  border-top: 1px solid var(--color-border-light);
}

.stat {
  text-align: center;
}

.stat-label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  margin-bottom: 2px;
}

.stat-value {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

/* ── Agent 流水线 ── */
.agent-pipeline {
  display: flex;
  align-items: center;
  gap: 0;
  padding: var(--space-md) 0;
}

.agent-node {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  opacity: 0.4;
  transition: all var(--transition-normal);
}

.agent-node.active {
  opacity: 1;
}

.agent-node.done {
  opacity: 0.7;
}

.agent-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-bg-page);
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  transition: all var(--transition-normal);
}

.agent-node.active .agent-icon {
  background: var(--color-primary-lighter);
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(22, 93, 255, 0.1);
}

.agent-node.done .agent-icon {
  background: var(--color-success-light);
  border-color: var(--color-success);
  color: var(--color-success);
}

.agent-name {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-weight: 500;
}

.agent-node.active .agent-name {
  color: var(--color-primary);
  font-weight: 600;
}

.agent-pipeline .agent-node:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 22px;
  left: calc(50% + 26px);
  right: calc(-50% + 26px);
  height: 2px;
  background: var(--color-border);
}

.agent-pipeline .agent-node.done:not(:last-child)::after {
  background: var(--color-success);
}

/* ── 日志终端 ── */
.log-terminal {
  background: #1a1a2e;
  border-radius: var(--radius-md);
  padding: var(--space-md);
  min-height: 240px;
  max-height: 400px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.log-empty {
  color: #4e5969;
  text-align: center;
  padding: var(--space-xl);
}

.log-line {
  display: flex;
  gap: var(--space-sm);
  padding: 2px 0;
}

.log-time {
  color: #4e5969;
  flex-shrink: 0;
}

.log-msg {
  color: #e5e6eb;
}

/* ── 章节列表 ── */
.chapter-list {
  max-height: 500px;
  overflow-y: auto;
}

.chapter-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.chapter-item:hover {
  background: var(--color-bg-page);
}

.chapter-item.active {
  background: var(--color-primary-lighter);
}

.ch-num {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  font-weight: 600;
  min-width: 24px;
}

.ch-title {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 流式内容预览 ── */
.streaming-card {
  border: 1px solid var(--color-warning-light);
}

.streaming-tag {
  margin-left: auto;
}

.streaming-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-warning);
  animation: pulse 1s ease-in-out infinite;
}

.streaming-content {
  background: #1a1a2e;
  color: #e5e6eb;
  border-radius: var(--radius-md);
  padding: var(--space-md);
  max-height: 400px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}

.cursor-blink {
  animation: blink 0.8s step-end infinite;
  color: var(--color-warning);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
