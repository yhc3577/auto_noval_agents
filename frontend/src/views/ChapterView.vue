<template>
  <div class="page-container" v-if="chapter">
    <div class="page-header">
      <h1 class="page-title">{{ formatChapterTitle(chapter.chapter_number, chapter.title) }}</h1>
      <div class="header-actions">
        <template v-if="!editing">
          <el-button :icon="Edit" @click="startEdit">编辑正文</el-button>
          <el-button :icon="MagicStick" @click="showPolishDialog(false)">AI润色</el-button>
          <el-button :icon="View" @click="doReview">AI审核</el-button>
          <el-button type="danger" :icon="Delete" @click="confirmDelete">删除</el-button>
        </template>
        <template v-else>
          <el-button @click="editing = false">取消</el-button>
          <el-button :icon="MagicStick" @click="showPolishDialog(true)">AI润色</el-button>
          <el-button :icon="View" @click="doReview">AI审核</el-button>
          <el-button type="primary" :icon="Check" @click="saveEdit">保存修改</el-button>
        </template>
      </div>
    </div>

    <div class="chapter-layout">
      <!-- 左侧正文区 -->
      <div class="chapter-main">
        <div class="section-card">
          <template v-if="!editing">
            <div class="content-area">{{ chapter.content || '暂无内容' }}</div>
          </template>
          <template v-else>
            <el-input v-model="editContent" type="textarea" :rows="30" class="editor-area" />
          </template>
        </div>
      </div>

      <!-- 右侧信息面板 -->
      <div class="chapter-sidebar">
        <!-- 章节信息 -->
        <div class="section-card">
          <div class="section-title">章节信息</div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">章号</span>
              <span class="info-value">第{{ toChineseNum(chapter.chapter_number) }}章</span>
            </div>
            <div class="info-item">
              <span class="info-label">字数</span>
              <span class="info-value">{{ chapter.word_count?.toLocaleString() }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">状态</span>
              <el-tag :type="statusType" size="small" effect="light">{{ statusText }}</el-tag>
            </div>
          </div>
        </div>

        <!-- 细纲 -->
        <div class="section-card" v-if="chapter.outline">
          <div class="section-title">章节细纲</div>
          <p class="outline-text">{{ chapter.outline }}</p>
        </div>

        <!-- 摘要 -->
        <div class="section-card" v-if="chapter.summary">
          <div class="section-title">章节摘要</div>
          <p class="summary-text">{{ chapter.summary }}</p>
        </div>

        <!-- 剧情审核 -->
        <div class="section-card" v-if="chapter.audit_records?.length">
          <div class="section-title">剧情审核</div>
          <div v-for="(record, i) in chapter.audit_records" :key="i" class="audit-item">
            <div class="audit-header">
              <el-tag :type="record.result === 'pass' ? 'success' : record.result === 'review' ? 'primary' : 'danger'" size="small" effect="light">
                {{ record.result === 'pass' ? '通过' : record.result === 'review' ? '人工审核' : '未通过' }}
              </el-tag>
              <span v-if="record.score" class="audit-score">{{ record.score }}分</span>
            </div>
            <p class="audit-opinion">{{ record.opinion }}</p>
          </div>
        </div>

        <!-- 版权报告 -->
        <div class="section-card" v-if="chapter.copyright_report">
          <div class="section-title">版权报告</div>
          <div class="copyright-grid">
            <div class="copyright-item">
              <el-progress
                type="dashboard"
                :percentage="chapter.copyright_report.originality_score"
                :color="chapter.copyright_report.originality_score >= 80 ? 'var(--color-success)' : 'var(--color-warning)'"
                :width="80"
                :stroke-width="6"
              />
              <span class="copyright-label">原创度</span>
            </div>
            <div class="copyright-item">
              <div class="copyright-stat">
                <span class="copyright-num">{{ (chapter.copyright_report.max_similarity * 100).toFixed(1) }}%</span>
                <span class="copyright-label">最高相似</span>
              </div>
            </div>
          </div>
          <div class="copyright-result">
            <el-tag :type="chapter.copyright_report.passed ? 'success' : 'danger'" effect="light">
              {{ chapter.copyright_report.passed ? '版权合规' : '相似度过高' }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- AI审核结果弹窗 -->
    <el-dialog v-model="reviewDialogVisible" title="AI审核意见" width="640px" :close-on-click-modal="false">
      <div v-loading="reviewLoading" class="review-content">
        <pre v-if="reviewResult" class="review-text">{{ reviewResult }}</pre>
      </div>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">关闭</el-button>
        <el-button v-if="reviewResult" type="primary" @click="applyReviewToEdit">应用到编辑器</el-button>
      </template>
    </el-dialog>

    <!-- AI润色弹窗 -->
    <el-dialog v-model="polishDialogVisible" title="AI润色" width="640px" :close-on-click-modal="false">
      <div v-loading="polishLoading">
        <div class="polish-form">
          <el-input
            v-model="polishInstruction"
            type="textarea"
            :rows="3"
            placeholder="可选：输入具体修改意见，如'加强对话的紧张感'、'第三段描写太啰嗦'等"
          />
        </div>
        <div v-if="polishResult" class="polish-preview">
          <div class="polish-preview-title">润色预览</div>
          <pre class="polish-text">{{ polishResult }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="polishDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="polishLoading" @click="doPolish">
          {{ polishResult ? '重新润色' : '开始润色' }}
        </el-button>
        <el-button v-if="polishResult" type="success" @click="applyPolish">应用润色结果</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Check, Delete, MagicStick, View } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const chapter = ref<any>(null)
const editing = ref(false)
const editContent = ref('')

// AI审核
const reviewDialogVisible = ref(false)
const reviewLoading = ref(false)
const reviewResult = ref('')

// AI润色
const polishDialogVisible = ref(false)
const polishLoading = ref(false)
const polishInstruction = ref('')
const polishResult = ref('')
const polishForEdit = ref(false) // 是否在编辑模式下润色

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
  if (/^第[一二三四五六七八九十百千\d]+章/.test(title)) {
    return title
  }
  const prefix = `第${toChineseNum(chapterNumber)}章`
  return title ? `${prefix}：${title}` : prefix
}

const statusMap: Record<string, { type: string; text: string }> = {
  completed: { type: 'success', text: '已完成' },
  writing: { type: 'warning', text: '写作中' },
  rewriting: { type: 'warning', text: '重写中' },
  manual_review: { type: 'danger', text: '人工介入' },
  failed: { type: 'danger', text: '失败' },
}

const statusType = computed(() => (statusMap[chapter.value?.status]?.type || 'info') as any)
const statusText = computed(() => statusMap[chapter.value?.status]?.text || chapter.value?.status)

onMounted(async () => {
  await loadChapter()
})

async function loadChapter() {
  const { data } = await api.get('/chapter/detail', { params: { chapter_id: route.params.chapterId } })
  chapter.value = data
}

function startEdit() {
  editContent.value = chapter.value.content || ''
  editing.value = true
}

async function saveEdit() {
  try {
    await api.put('/chapter/edit', { chapter_id: chapter.value.chapter_id, content: editContent.value })
    chapter.value.content = editContent.value
    chapter.value.word_count = editContent.value.length
    editing.value = false
    ElMessage.success('保存成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function confirmDelete() {
  try {
    await ElMessageBox.confirm(
      `确定删除「${chapter.value.title}」吗？此操作不可撤销。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete('/chapter/delete', { params: { chapter_id: chapter.value.chapter_id } })
    ElMessage.success('章节已删除')
    router.push(`/novel/${route.params.id}/console`)
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

async function doReview() {
  reviewDialogVisible.value = true
  reviewLoading.value = true
  reviewResult.value = ''
  try {
    const { data } = await api.post('/chapter/review', { chapter_id: chapter.value.chapter_id })
    reviewResult.value = data.review
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'AI审核失败')
    reviewDialogVisible.value = false
  } finally {
    reviewLoading.value = false
  }
}

function applyReviewToEdit() {
  if (!editing.value) {
    startEdit()
  }
  reviewDialogVisible.value = false
  ElMessage.info('审核意见已参考，请在编辑器中修改')
}

function showPolishDialog(forEdit: boolean) {
  polishForEdit.value = forEdit
  polishInstruction.value = ''
  polishResult.value = ''
  polishDialogVisible.value = true
}

async function doPolish() {
  polishLoading.value = true
  polishResult.value = ''
  try {
    const content = polishForEdit.value ? editContent.value : chapter.value.content
    const { data } = await api.post('/chapter/polish', {
      chapter_id: chapter.value.chapter_id,
      content,
      instruction: polishInstruction.value,
    })
    polishResult.value = data.content
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'AI润色失败')
  } finally {
    polishLoading.value = false
  }
}

function applyPolish() {
  if (polishForEdit.value) {
    editContent.value = polishResult.value
  } else {
    editContent.value = polishResult.value
    editing.value = true
  }
  polishDialogVisible.value = false
  ElMessage.success('润色结果已应用到编辑器，请检查后保存')
}
</script>

<style scoped>
.chapter-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: var(--space-lg);
  align-items: start;
}

.header-actions {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.content-area {
  line-height: 2;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
  white-space: pre-wrap;
  font-family: var(--font-family);
}

.editor-area :deep(textarea) {
  font-size: var(--font-size-md);
  line-height: 1.8;
  font-family: var(--font-family);
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.info-value {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
}

.outline-text,
.summary-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.7;
  white-space: pre-wrap;
}

.audit-item {
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--color-border-light);
}

.audit-item:last-child { border-bottom: none; }

.audit-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 4px;
}

.audit-score {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.audit-opinion {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.6;
}

.copyright-grid {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: var(--space-md) 0;
}

.copyright-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
}

.copyright-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.copyright-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.copyright-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.copyright-result {
  text-align: center;
  padding-top: var(--space-sm);
  border-top: 1px solid var(--color-border-light);
}

.review-content {
  min-height: 200px;
}

.review-text,
.polish-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-regular);
  background: var(--color-bg-page);
  padding: var(--space-md);
  border-radius: var(--border-radius-base);
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
  font-family: inherit;
}

.polish-form {
  margin-bottom: var(--space-md);
}

.polish-preview {
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--space-md);
}

.polish-preview-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  margin-bottom: var(--space-sm);
  color: var(--color-text-primary);
}
</style>
