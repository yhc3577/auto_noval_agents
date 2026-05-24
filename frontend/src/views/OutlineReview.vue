<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h1 class="page-title">大纲审核 - {{ novel?.title }}</h1>
      <div class="header-actions">
        <el-button @click="router.back()">返回</el-button>
        <el-button type="danger" :icon="Close" @click="handleReject" :loading="submitting" :disabled="novel?.outline_status === 'completed'">
          驳回
        </el-button>
        <el-button type="success" :icon="Check" @click="handleApprove" :loading="submitting" :disabled="novel?.outline_status === 'completed'">
          审核通过
        </el-button>
      </div>
    </div>

    <el-alert v-if="novel?.outline_status === 'completed'" title="该大纲已审核通过" type="success" show-icon :closable="false" style="margin-bottom: var(--space-lg)" />
    <el-alert v-else-if="novel?.outline_status === 'rejected'" :title="'大纲已驳回' + (novel.review_feedback ? '：' + novel.review_feedback : '')" type="warning" show-icon :closable="false" style="margin-bottom: var(--space-lg)" />

    <div class="review-layout" v-if="novel?.outline">
      <!-- 左侧：大纲内容 -->
      <div class="review-main">
        <!-- 全书大纲 -->
        <div class="section-card">
          <div class="section-title">
            全书大纲
            <div class="section-actions">
              <el-button
                v-if="novel.outline_status !== 'completed'"
                size="small"
                type="warning"
                :icon="MagicStick"
                :loading="reviewingFull"
                @click="reviewSection('full_outline')"
              >
                AI 审核
              </el-button>
              <el-button size="small" @click="editSection('full')" :disabled="novel.outline_status === 'completed'">
                <el-icon><Edit /></el-icon>手动编辑
              </el-button>
            </div>
          </div>

          <!-- 手动编辑 -->
          <div v-if="editingFull" class="edit-area">
            <el-input v-model="editFullOutline" type="textarea" :rows="8" placeholder="输入全书大纲..." />
            <div class="edit-actions">
              <el-button @click="editingFull = false">取消</el-button>
              <el-button type="primary" @click="saveSection('full')" :loading="saving">保存</el-button>
            </div>
          </div>

          <!-- Diff 对比面板 -->
          <div v-else-if="diffFull !== null" class="diff-panel">
            <div class="diff-header">
              <div class="diff-label original">原始版本</div>
              <div class="diff-label modified">AI 修改版本</div>
            </div>
            <div class="diff-body">
              <div class="diff-side original">
                <pre>{{ novel.outline.full_outline }}</pre>
              </div>
              <div class="diff-side modified">
                <pre>{{ diffFull }}</pre>
              </div>
            </div>
            <div class="diff-feedback">
              <el-input
                v-model="diffFeedback"
                placeholder="给 AI 提修改意见，如：增加悬念、节奏再快一些..."
                :disabled="refining"
                @keydown.enter.exact.prevent="refineModification('full_outline')"
              />
              <el-button type="warning" :icon="MagicStick" :loading="refining" @click="refineModification('full_outline')" :disabled="!diffFeedback.trim()">
                重新修改
              </el-button>
            </div>
            <div class="diff-footer">
              <el-button @click="diffFull = null; diffFeedback = ''">放弃</el-button>
              <el-button type="primary" @click="acceptDiff('full_outline')" :loading="saving">
                <el-icon><Check /></el-icon>应用修改
              </el-button>
            </div>
          </div>

          <!-- 正常显示 -->
          <div v-else class="outline-content">{{ novel.outline.full_outline }}</div>
        </div>

        <!-- 分卷大纲 -->
        <div class="section-card">
          <div class="section-title">分卷大纲（共 {{ novel.outline.volume_outlines?.length || 0 }} 卷）</div>
          <div v-if="novel.outline.volume_outlines?.length">
            <div v-for="(vol, vi) in novel.outline.volume_outlines" :key="vi" class="volume-block">
              <div class="volume-header">
                <span class="volume-label">第 {{ vol.volume_number || vi + 1 }} 卷{{ vol.volume_title ? '：' + vol.volume_title : '' }}</span>
                <div class="section-actions">
                  <el-button
                    v-if="novel.outline_status !== 'completed'"
                    size="small"
                    type="warning"
                    :icon="MagicStick"
                    :loading="reviewingVolume === vi"
                    @click="reviewSection('volume_outline', vi)"
                  >
                    AI 审核
                  </el-button>
                  <el-button v-if="novel.outline_status !== 'completed'" size="small" text @click="editVolumeItem(vi, vol)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                </div>
              </div>

              <!-- Diff 面板 -->
              <div v-if="diffVolume === vi" class="diff-panel">
                <div class="diff-header">
                  <div class="diff-label original">原始版本</div>
                  <div class="diff-label modified">AI 修改版本</div>
                </div>
                <div class="diff-body">
                  <div class="diff-side original">
                    <pre>{{ typeof vol === 'string' ? vol : vol.content }}</pre>
                  </div>
                  <div class="diff-side modified">
                    <pre>{{ extractContent(diffVolumeContent) }}</pre>
                  </div>
                </div>
                <div class="diff-feedback">
                  <el-input
                    v-model="diffFeedback"
                    placeholder="给 AI 提修改意见..."
                    :disabled="refining"
                    @keydown.enter.exact.prevent="refineModification('volume_outline', vi)"
                  />
                  <el-button type="warning" :icon="MagicStick" :loading="refining" @click="refineModification('volume_outline', vi)" :disabled="!diffFeedback.trim()">
                    重新修改
                  </el-button>
                </div>
                <div class="diff-footer">
                  <el-button @click="diffVolume = -1; diffVolumeContent = ''; diffFeedback = ''">放弃</el-button>
                  <el-button type="primary" @click="acceptDiff('volume_outline', vi)" :loading="saving">
                    <el-icon><Check /></el-icon>应用修改
                  </el-button>
                </div>
              </div>

              <!-- 手动编辑 -->
              <div v-else-if="editingVolume === vi" class="edit-area">
                <el-input v-model="editVolTitle" placeholder="分卷标题" style="margin-bottom: 8px" />
                <el-input v-model="editVolContent" type="textarea" :rows="4" placeholder="输入分卷大纲内容..." />
                <div class="edit-actions">
                  <el-button @click="editingVolume = -1">取消</el-button>
                  <el-button type="primary" @click="saveVolume(vi)" :loading="saving">保存</el-button>
                </div>
              </div>

              <!-- 正常 -->
              <div v-else class="volume-content">
                <p>{{ typeof vol === 'string' ? vol : vol.content }}</p>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无分卷大纲" :image-size="60" />
        </div>

        <!-- 逐章细纲 -->
        <div class="section-card">
          <div class="section-title">
            逐章细纲（共 {{ novel.outline.chapter_outlines?.length || 0 }} 章）
            <el-button
              v-if="novel.outline_status !== 'completed' && novel.outline.chapter_outlines?.length"
              size="small"
              type="warning"
              :icon="MagicStick"
              :loading="reviewingAllChapters"
              @click="reviewAllChapters"
              style="margin-left: var(--space-md)"
            >
              全部审核
            </el-button>
          </div>
          <div class="chapter-outline-list" v-if="novel.outline.chapter_outlines?.length">
            <div v-for="(ch, ci) in novel.outline.chapter_outlines" :key="ci" class="chapter-outline-item">
              <div class="ch-header">
                <span class="ch-number">第 {{ ch.chapter_number }} 章</span>
                <span class="ch-title-text">{{ ch.title }}</span>
                <div class="section-actions">
                  <el-button
                    v-if="novel.outline_status !== 'completed'"
                    size="small"
                    type="warning"
                    :icon="MagicStick"
                    :loading="reviewingChapter === ci"
                    @click="reviewSection('chapter_outline', ci)"
                  >
                    AI 审核
                  </el-button>
                  <el-button v-if="novel.outline_status !== 'completed'" size="small" text @click="editChapterItem(ci, ch)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                </div>
              </div>

              <!-- Diff 面板 -->
              <div v-if="diffChapter === ci" class="diff-panel">
                <div class="diff-header">
                  <div class="diff-label original">原始版本</div>
                  <div class="diff-label modified">AI 修改版本</div>
                </div>
                <div class="diff-body">
                  <div class="diff-side original">
                    <pre>{{ ch.content }}</pre>
                  </div>
                  <div class="diff-side modified">
                    <pre>{{ extractContent(diffChapterContent) }}</pre>
                  </div>
                </div>
                <div class="diff-feedback">
                  <el-input
                    v-model="diffFeedback"
                    placeholder="给 AI 提修改意见，如：增加反转、角色对话更自然一些..."
                    :disabled="refining"
                    @keydown.enter.exact.prevent="refineModification('chapter_outline', ci)"
                  />
                  <el-button type="warning" :icon="MagicStick" :loading="refining" @click="refineModification('chapter_outline', ci)" :disabled="!diffFeedback.trim()">
                    重新修改
                  </el-button>
                </div>
                <div class="diff-footer">
                  <el-button @click="diffChapter = -1; diffChapterContent = ''; diffFeedback = ''">放弃</el-button>
                  <el-button type="primary" @click="acceptDiff('chapter_outline', ci)" :loading="saving">
                    <el-icon><Check /></el-icon>应用修改
                  </el-button>
                </div>
              </div>

              <!-- 正常显示 -->
              <p v-else class="ch-content">{{ ch.content }}</p>
            </div>
          </div>
          <el-empty v-else description="暂无章节细纲" :image-size="60" />
        </div>
      </div>

      <!-- 右侧：AI 审核助手对话面板 -->
      <div class="review-sidebar">
        <div class="chat-panel">
          <div class="chat-header">
            <div class="chat-title">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI 审核助手</span>
            </div>
            <el-button text size="small" @click="clearChat" :disabled="messages.length === 0">清空</el-button>
          </div>

          <div class="quick-actions" v-if="novel.outline_status !== 'completed'">
            <el-button size="small" @click="sendQuickAction(act.prompt)" :disabled="chatting" v-for="act in quickActions" :key="act.label">
              {{ act.label }}
            </el-button>
          </div>

          <div class="chat-messages" ref="chatMsgsRef">
            <div v-if="messages.length === 0" class="chat-empty">
              <el-icon :size="32"><ChatDotRound /></el-icon>
              <p>点击左侧「AI 审核」按钮逐项审核</p>
              <p class="chat-empty-hint">或在此提出整体修改意见</p>
            </div>
            <div v-for="(msg, i) in messages" :key="i" class="chat-msg" :class="msg.role">
              <div class="msg-avatar">
                <el-icon v-if="msg.role === 'assistant'" :size="18"><Cpu /></el-icon>
                <el-icon v-else :size="18"><User /></el-icon>
              </div>
              <div class="msg-body">
                <div class="msg-content" v-text="msg.content"></div>
                <div v-if="msg.role === 'assistant' && msg.content && !chatting" class="msg-actions">
                  <el-button size="small" text @click="copyMsg(msg.content)">
                    <el-icon><CopyDocument /></el-icon>复制
                  </el-button>
                </div>
              </div>
            </div>
            <div v-if="chatting" class="chat-msg assistant">
              <div class="msg-avatar"><el-icon :size="18"><Cpu /></el-icon></div>
              <div class="msg-body">
                <div class="msg-content streaming">{{ streamingText }}<span class="cursor-blink">|</span></div>
              </div>
            </div>
          </div>

          <div class="chat-input-area" v-if="novel.outline_status !== 'completed'">
            <el-input v-model="inputMsg" type="textarea" :rows="2" placeholder="输入整体修改意见..." :disabled="chatting" @keydown.enter.exact.prevent="sendMessage" />
            <el-button type="primary" :icon="Promotion" :loading="chatting" :disabled="!inputMsg.trim()" @click="sendMessage" style="margin-top: 8px; width: 100%">发送</el-button>
          </div>
          <div v-else class="chat-completed-hint">
            <el-icon><CircleCheck /></el-icon>
            <span>大纲已审核通过</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="驳回大纲" width="500px" :close-on-click-modal="false">
      <el-form>
        <el-form-item label="驳回理由">
          <el-input v-model="rejectFeedback" type="textarea" :rows="4" placeholder="请说明驳回原因..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :loading="submitting">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import {
  Check, Close, Edit, ChatDotRound, Cpu, User,
  Promotion, CopyDocument, CircleCheck, MagicStick
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()

const novel = ref<any>(null)
const loading = ref(false)
const saving = ref(false)
const submitting = ref(false)

// 编辑状态
const editingFull = ref(false)
const editFullOutline = ref('')
const editingVolume = ref(-1)
const editVolTitle = ref('')
const editVolContent = ref('')
const rejectDialogVisible = ref(false)
const rejectFeedback = ref('')

// AI 逐项审核状态
const reviewingFull = ref(false)
const reviewingVolume = ref(-1)
const reviewingChapter = ref(-1)
const reviewingAllChapters = ref(false)

// Diff 状态
const diffFull = ref<string | null>(null)
const diffVolume = ref(-1)
const diffVolumeContent = ref('')
const diffChapter = ref(-1)
const diffChapterContent = ref('')
const diffFeedback = ref('')
const refining = ref(false)

// 聊天
const chatMsgsRef = ref<HTMLElement>()
const messages = ref<{ role: string; content: string }[]>([])
const inputMsg = ref('')
const chatting = ref(false)
const streamingText = ref('')
let abortController: AbortController | null = null

const quickActions = [
  { label: '评价整体结构', prompt: '请评价这个大纲的整体结构、节奏和冲突设计。' },
  { label: '分析角色弧线', prompt: '请分析主要角色的弧线设计是否完整。' },
  { label: '检查首尾呼应', prompt: '请检查开篇和结尾是否有呼应，整体是否闭环。' },
  { label: '改进建议', prompt: '请给出3-5条最关键的改进建议。' },
]

onMounted(async () => { await loadNovel() })

async function loadNovel() {
  loading.value = true
  try {
    novel.value = await novelStore.fetchNovelDetail(route.params.id as string)
  } finally {
    loading.value = false
  }
}

// ── 手动编辑 ──

function editSection(type: string) {
  if (type === 'full') {
    editFullOutline.value = novel.value.outline.full_outline
    editingFull.value = true
  }
}

async function saveSection(type: string) {
  saving.value = true
  try {
    const payload: any = { project_id: novel.value.project_id }
    if (type === 'full') payload.full_outline = editFullOutline.value
    await novelStore.updateOutline(payload)
    novel.value.outline.full_outline = editFullOutline.value
    editingFull.value = false
    ElMessage.success('全书大纲已更新')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

function editVolumeItem(index: number, vol: any) {
  const v = typeof vol === 'string' ? { volume_title: '', content: vol } : vol
  editVolTitle.value = v.volume_title || ''
  editVolContent.value = v.content || ''
  editingVolume.value = index
}

async function saveVolume(index: number) {
  saving.value = true
  try {
    const volumes = [...novel.value.outline.volume_outlines]
    volumes[index] = { ...volumes[index], volume_title: editVolTitle.value, content: editVolContent.value }
    await novelStore.updateOutline({ project_id: novel.value.project_id, volume_outlines: volumes })
    novel.value.outline.volume_outlines = volumes
    editingVolume.value = -1
    ElMessage.success('分卷大纲已更新')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

function editChapterItem(index: number, ch: any) {
  const newTitle = prompt('章节标题', ch.title)
  if (newTitle === null) return
  const newContent = prompt('章节内容', ch.content)
  if (newContent === null) return
  updateChapter(index, newTitle, newContent)
}

async function updateChapter(index: number, title: string, content: string) {
  saving.value = true
  try {
    const chapters = [...novel.value.outline.chapter_outlines]
    chapters[index] = { ...chapters[index], title, content }
    await novelStore.updateOutline({ project_id: novel.value.project_id, chapter_outlines: chapters })
    novel.value.outline.chapter_outlines = chapters
    ElMessage.success('章节细纲已更新')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally { saving.value = false }
}

// ── 审核操作 ──

function handleReject() { rejectFeedback.value = ''; rejectDialogVisible.value = true }

async function confirmReject() {
  submitting.value = true
  try {
    await novelStore.reviewOutline(novel.value.project_id, false, rejectFeedback.value)
    novel.value.outline_status = 'rejected'
    novel.value.review_feedback = rejectFeedback.value
    rejectDialogVisible.value = false
    ElMessage.warning('大纲已驳回')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally { submitting.value = false }
}

async function handleApprove() {
  submitting.value = true
  try {
    await novelStore.reviewOutline(novel.value.project_id, true)
    novel.value.outline_status = 'completed'
    ElMessage.success('大纲审核通过，可以开始创作')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally { submitting.value = false }
}

// ── AI 逐项审核 ──

async function reviewSection(targetType: string, targetIndex?: number) {
  // 设置 loading 状态
  if (targetType === 'full_outline') reviewingFull.value = true
  else if (targetType === 'volume_outline') reviewingVolume.value = targetIndex ?? -1
  else if (targetType === 'chapter_outline') reviewingChapter.value = targetIndex ?? -1

  try {
    const { data } = await api.post('/novel/outline/review-section', {
      project_id: novel.value.project_id,
      target_type: targetType,
      target_index: targetIndex,
    })

    // 显示 diff
    if (targetType === 'full_outline') {
      diffFull.value = data.modified
    } else if (targetType === 'volume_outline') {
      diffVolume.value = targetIndex ?? 0
      diffVolumeContent.value = data.modified
    } else if (targetType === 'chapter_outline') {
      diffChapter.value = targetIndex ?? 0
      diffChapterContent.value = data.modified
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'AI 审核失败')
  } finally {
    if (targetType === 'full_outline') reviewingFull.value = false
    else if (targetType === 'volume_outline') reviewingVolume.value = -1
    else if (targetType === 'chapter_outline') reviewingChapter.value = -1
  }
}

async function reviewAllChapters() {
  const chapters = novel.value.outline.chapter_outlines
  if (!chapters?.length) return

  reviewingAllChapters.value = true
  let applied = 0

  for (let ci = 0; ci < chapters.length; ci++) {
    reviewingChapter.value = ci
    try {
      const { data } = await api.post('/novel/outline/review-section', {
        project_id: novel.value.project_id,
        target_type: 'chapter_outline',
        target_index: ci,
      })
      // Parse modified content with markdown fence cleanup
      let parsed: any
      const cleaned = cleanJsonText(data.modified)
      try {
        parsed = JSON.parse(cleaned)
      } catch {
        parsed = { title: chapters[ci].title, content: cleaned || data.modified }
      }
      chapters[ci] = {
        ...chapters[ci],
        title: parsed.title || chapters[ci].title,
        content: parsed.content || cleaned || data.modified,
      }
      applied++
    } catch {
      // Skip chapters that fail
    }
  }

  if (applied > 0) {
    try {
      await novelStore.updateOutline({
        project_id: novel.value.project_id,
        chapter_outlines: chapters,
      })
      novel.value.outline.chapter_outlines = chapters
      ElMessage.success(`已自动审核并应用 ${applied} 章`)
    } catch (error: any) {
      ElMessage.error('保存失败: ' + (error.response?.data?.detail || ''))
    }
  }

  reviewingChapter.value = -1
  reviewingAllChapters.value = false
}

function parseOutlineJson(text: string, fallbackTitle?: string): { title?: string; volume_title?: string; content: string } {
  const cleaned = cleanJsonText(text)
  try {
    return JSON.parse(cleaned)
  } catch {
    // 解析失败时，尝试从 JSON 字符串中提取 content 字段
    const contentMatch = cleaned.match(/"(?:content|volume_title|title)"\s*:\s*"((?:[^"\\]|\\.)*)"/)
    if (contentMatch) {
      return { content: contentMatch[1] }
    }
    // 最终兜底：使用清理后的原文
    return { title: fallbackTitle, content: cleaned }
  }
}

async function acceptDiff(targetType: string, targetIndex?: number) {
  saving.value = true
  try {
    const payload: any = { project_id: novel.value.project_id }

    if (targetType === 'full_outline') {
      payload.full_outline = diffFull.value
      await novelStore.updateOutline(payload)
      novel.value.outline.full_outline = diffFull.value
      diffFull.value = null
    } else if (targetType === 'volume_outline' && targetIndex !== undefined) {
      const vol = novel.value.outline.volume_outlines[targetIndex]
      const parsed = parseOutlineJson(diffVolumeContent.value, vol.volume_title)
      const volumes = [...novel.value.outline.volume_outlines]
      volumes[targetIndex] = {
        ...vol,
        volume_title: parsed.volume_title || vol.volume_title,
        content: parsed.content,
      }
      payload.volume_outlines = volumes
      await novelStore.updateOutline(payload)
      novel.value.outline.volume_outlines = volumes
      diffVolume.value = -1
      diffVolumeContent.value = ''
    } else if (targetType === 'chapter_outline' && targetIndex !== undefined) {
      const ch = novel.value.outline.chapter_outlines[targetIndex]
      const parsed = parseOutlineJson(diffChapterContent.value, ch.title)
      const chapters = [...novel.value.outline.chapter_outlines]
      chapters[targetIndex] = {
        ...ch,
        title: parsed.title || ch.title,
        content: parsed.content,
      }
      payload.chapter_outlines = chapters
      await novelStore.updateOutline(payload)
      novel.value.outline.chapter_outlines = chapters
      diffChapter.value = -1
      diffChapterContent.value = ''
    }

    ElMessage.success('修改已应用')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '应用失败')
  } finally { saving.value = false }
}

function cleanJsonText(text: string): string {
  return text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim()
}

function extractContent(text: string): string {
  const cleaned = cleanJsonText(text)
  try {
    const parsed = JSON.parse(cleaned)
    return parsed.content || text
  } catch {
    return cleaned
  }
}

// ── 交互式重新修改 ──

async function refineModification(targetType: string, targetIndex?: number) {
  const feedback = diffFeedback.value.trim()
  if (!feedback || refining.value) return

  refining.value = true
  try {
    const { data } = await api.post('/novel/outline/review-section', {
      project_id: novel.value.project_id,
      target_type: targetType,
      target_index: targetIndex,
      instruction: feedback,
    })

    // 更新 diff 内容
    if (targetType === 'full_outline') {
      diffFull.value = data.modified
    } else if (targetType === 'volume_outline') {
      diffVolumeContent.value = data.modified
    } else if (targetType === 'chapter_outline') {
      diffChapterContent.value = data.modified
    }

    diffFeedback.value = ''
    ElMessage.success('AI 已根据意见重新修改')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '重新修改失败')
  } finally {
    refining.value = false
  }
}

// ── AI 聊天 ──

function clearChat() { messages.value = [] }

function copyMsg(content: string) {
  navigator.clipboard.writeText(content).then(() => ElMessage.success('已复制'))
}

async function sendQuickAction(prompt: string) {
  inputMsg.value = prompt
  await sendMessage()
}

async function sendMessage() {
  const msg = inputMsg.value.trim()
  if (!msg || chatting.value) return

  inputMsg.value = ''
  messages.value.push({ role: 'user', content: msg })
  chatting.value = true
  streamingText.value = ''

  await nextTick(); scrollChatBottom()

  const token = localStorage.getItem('token')
  abortController = new AbortController()

  try {
    const response = await fetch('/api/novel/outline/chat?token=' + encodeURIComponent(token || ''), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: novel.value.project_id,
        message: msg,
        history: messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
      }),
      signal: abortController.signal,
    })

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'chunk') {
            streamingText.value += data.content
            await nextTick(); scrollChatBottom()
          } else if (data.type === 'done') {
            messages.value.push({ role: 'assistant', content: data.content })
            streamingText.value = ''
          } else if (data.type === 'error') {
            messages.value.push({ role: 'assistant', content: '[错误] ' + data.content })
            streamingText.value = ''
          }
        } catch {}
      }
    }
  } catch (error: any) {
    if (error.name !== 'AbortError') {
      messages.value.push({ role: 'assistant', content: '[请求失败] ' + (error.message || '网络错误') })
      streamingText.value = ''
    }
  } finally {
    chatting.value = false
    abortController = null
    await nextTick(); scrollChatBottom()
  }
}

function scrollChatBottom() {
  nextTick(() => {
    if (chatMsgsRef.value) chatMsgsRef.value.scrollTop = chatMsgsRef.value.scrollHeight
  })
}
</script>

<style scoped>
.review-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: var(--space-lg);
  align-items: start;
}
.review-main { min-width: 0; }
.review-sidebar { position: sticky; top: calc(var(--topbar-height) + var(--space-lg)); }
.header-actions { display: flex; gap: var(--space-sm); }

/* ── 通用 ── */
.section-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.outline-content {
  color: var(--color-text-regular);
  line-height: 1.8;
  white-space: pre-wrap;
}

.volume-block {
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--color-border-light);
}
.volume-block:last-child { border-bottom: none; }

.volume-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}
.volume-label {
  font-weight: 600;
  color: var(--color-primary);
  font-size: var(--font-size-md);
}

.volume-content {
  color: var(--color-text-regular);
  line-height: 1.7;
  white-space: pre-wrap;
}

.edit-area { margin-top: var(--space-sm); }
.edit-actions { display: flex; gap: var(--space-sm); margin-top: var(--space-sm); justify-content: flex-end; }

.chapter-outline-list { max-height: none; }
.chapter-outline-item {
  padding: var(--space-md);
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--transition-fast);
}
.chapter-outline-item:last-child { border-bottom: none; }

.ch-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 6px;
}
.ch-number { font-weight: 600; color: var(--color-primary); font-size: var(--font-size-sm); flex-shrink: 0; }
.ch-title-text { font-weight: 500; color: var(--color-text-primary); flex: 1; }
.ch-content { font-size: var(--font-size-sm); color: var(--color-text-secondary); line-height: 1.7; }

/* ── Diff 对比面板 ── */
.diff-panel {
  margin-top: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.diff-header {
  display: flex;
  background: var(--color-bg-page);
  border-bottom: 1px solid var(--color-border);
}

.diff-label {
  flex: 1;
  padding: 6px var(--space-md);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-align: center;
}
.diff-label.original {
  color: #c0392b;
  background: #fdecea;
  border-right: 1px solid var(--color-border);
}
.diff-label.modified {
  color: #27ae60;
  background: #eafaf1;
}

.diff-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  max-height: 400px;
  overflow-y: auto;
}

.diff-side {
  padding: var(--space-md);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.diff-side.original {
  background: #fef5f5;
  border-right: 1px solid var(--color-border);
  color: #c0392b;
}
.diff-side.modified {
  background: #f5fef8;
  color: #27ae60;
}
.diff-side pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.diff-feedback {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--color-bg-page);
  border-top: 1px solid var(--color-border);
  align-items: center;
}
.diff-feedback .el-input { flex: 1; }

.diff-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--color-bg-page);
  border-top: 1px solid var(--color-border);
}

/* ── AI 聊天面板 ── */
.chat-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 240px);
  min-height: 500px;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md);
  border-bottom: 1px solid var(--color-border-light);
}
.chat-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}
.chat-title .el-icon { color: var(--color-primary); }
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--color-border-light);
}
.chat-messages { flex: 1; overflow-y: auto; padding: var(--space-md); }
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-text-placeholder);
  text-align: center;
  gap: var(--space-sm);
}
.chat-empty-hint { font-size: var(--font-size-xs); }
.chat-msg { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
.chat-msg.user { flex-direction: row-reverse; }
.chat-msg.user .msg-body {
  background: var(--color-primary-lighter);
  border-radius: var(--radius-md) 4px var(--radius-md) var(--radius-md);
}
.chat-msg.assistant .msg-body {
  background: var(--color-bg-page);
  border-radius: 4px var(--radius-md) var(--radius-md) var(--radius-md);
}
.msg-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
}
.chat-msg.user .msg-avatar { background: var(--color-primary-lighter); color: var(--color-primary); }
.chat-msg.assistant .msg-avatar { background: var(--color-primary-lighter); color: var(--color-primary); }
.msg-body {
  padding: var(--space-sm) var(--space-md);
  max-width: 85%;
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--color-text-regular);
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}
.msg-content.streaming { color: var(--color-text-primary); }
.msg-actions { margin-top: 4px; display: flex; gap: 4px; }
.cursor-blink { animation: blink 0.8s step-end infinite; color: var(--color-primary); }
.chat-input-area { padding: var(--space-md); border-top: 1px solid var(--color-border-light); }
.chat-completed-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-lg);
  color: var(--color-success);
  font-size: var(--font-size-sm);
  border-top: 1px solid var(--color-border-light);
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
