<template>
  <div class="page-container" v-if="novel">
    <div class="page-header">
      <h1 class="page-title">{{ novel.title }}</h1>
      <div class="header-actions">
        <el-button
          v-if="novel.outline_status === 'review' || novel.outline_status === 'rejected'"
          type="warning"
          :icon="Checked"
          @click="router.push(`/novel/${novel.project_id}/review`)"
        >
          审核大纲
        </el-button>
        <el-button type="primary" :icon="Monitor" @click="router.push(`/novel/${novel.project_id}/console`)">
          创作控制台
        </el-button>
        <el-button :icon="Download" @click="router.push(`/novel/${novel.project_id}/export`)">
          导出小说
        </el-button>
        <el-button :icon="Edit" @click="showEditDialog" :disabled="novel.status === 'writing'">
          编辑
        </el-button>
        <el-button type="danger" :icon="Delete" @click="handleDelete" :disabled="novel.status === 'writing'">
          删除
        </el-button>
      </div>
    </div>

    <div class="detail-layout">
      <!-- 左侧主内容 -->
      <div class="detail-main">
        <!-- 项目信息卡片 -->
        <div class="section-card">
          <div class="section-title">项目信息</div>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="题材">{{ novel.genre }}</el-descriptions-item>
            <el-descriptions-item label="文风">{{ novel.style }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusMap[novel.status]?.type" effect="light">
                {{ statusMap[novel.status]?.text }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="总章节">{{ novel.chapter_count }} 章</el-descriptions-item>
            <el-descriptions-item label="每章字数">{{ novel.words_per_chapter }} 字</el-descriptions-item>
            <el-descriptions-item label="当前进度">{{ novel.current_chapter }}/{{ novel.chapter_count }}</el-descriptions-item>
          </el-descriptions>

          <div class="world-setting">
            <div class="section-title" style="margin-top: var(--space-lg)">世界观设定</div>
            <p class="world-text">{{ novel.world_setting }}</p>
          </div>
        </div>

        <!-- 大纲生成中 -->
        <div class="section-card" v-if="novel.outline_status === 'pending' || novel.outline_status === 'generating'">
          <div class="section-title">大纲生成中</div>
          <div class="outline-generating">
            <el-icon class="generating-spin" :size="24"><Loading /></el-icon>
            <span>大纲正在后台生成中，请稍候...</span>
            <p class="generating-hint">生成过程可能需要 1-2 分钟，页面会自动刷新</p>
          </div>
        </div>

        <!-- 大纲生成失败 -->
        <div class="section-card" v-else-if="novel.outline_status === 'failed'">
          <div class="section-title">大纲生成</div>
          <el-alert title="大纲生成失败" type="error" show-icon :closable="false">
            <template #default>
              <p>大纲生成过程中出现错误，请点击下方按钮重新生成。</p>
            </template>
          </el-alert>
          <el-button type="primary" @click="handleRegenerate" :loading="regenerating" style="margin-top: 12px">
            重新生成大纲
          </el-button>
        </div>

        <!-- 待审核提示 -->
        <el-alert
          v-if="novel.outline_status === 'review'"
          title="大纲已生成，请审核通过后再开始创作"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: var(--space-md)"
        />

        <!-- 已驳回提示 -->
        <el-alert
          v-else-if="novel.outline_status === 'rejected'"
          :title="'大纲已驳回，请修改后重新审核' + (novel.review_feedback ? '：' + novel.review_feedback : '')"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: var(--space-md)"
        />

        <!-- 大纲内容 -->
        <div class="section-card" v-if="novel.outline">
          <div class="section-title">
            全书大纲
            <el-button size="small" @click="handleRegenerate" :loading="regenerating" :disabled="novel.status === 'writing'" style="margin-left: auto">
              重新生成大纲
            </el-button>
          </div>
          <div class="outline-content">{{ novel.outline.full_outline }}</div>

          <template v-if="novel.outline.volume_outlines?.length">
            <el-divider />
            <div class="section-title">分卷大纲</div>
            <div v-for="(vol, i) in novel.outline.volume_outlines" :key="i" class="volume-item">
              <h4>第 {{ i + 1 }} 卷</h4>
              <p>{{ typeof vol === 'string' ? vol : vol.content }}</p>
            </div>
          </template>
        </div>
      </div>

      <!-- 右侧边栏 -->
      <div class="detail-sidebar">
        <!-- 角色列表 -->
        <div class="section-card">
          <div class="section-title">角色设定</div>
          <div v-for="char in novel.characters" :key="char.name" class="character-item">
            <div class="character-header">
              <span class="character-name">{{ char.name }}</span>
              <el-tag :type="roleTagType(char.role_type)" size="small" effect="plain">
                {{ roleLabels[char.role_type] }}
              </el-tag>
            </div>
            <p class="character-personality">{{ char.personality }}</p>
            <p class="character-background">{{ char.background }}</p>
          </div>
          <el-empty v-if="!novel.characters?.length" description="暂无角色" :image-size="60" />
        </div>

        <!-- 章节进度 -->
        <div class="section-card" v-if="novel.status === 'writing' || novel.current_chapter > 0">
          <div class="section-title">创作进度</div>
          <el-progress
            type="dashboard"
            :percentage="Math.round((novel.current_chapter / novel.chapter_count) * 100)"
            :color="progressColors"
            :width="160"
          >
            <template #default="{ percentage }">
              <div class="progress-center">
                <span class="progress-pct">{{ percentage }}%</span>
                <span class="progress-label">{{ novel.current_chapter }}/{{ novel.chapter_count }} 章</span>
              </div>
            </template>
          </el-progress>
        </div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑项目设定" width="600px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="文风">
          <el-input v-model="editForm.style" placeholder="如：轻松幽默、严肃深沉" />
        </el-form-item>
        <el-form-item label="世界观设定">
          <el-input v-model="editForm.world_setting" type="textarea" :rows="6" placeholder="详细描述小说的世界观" />
        </el-form-item>
        <el-form-item label="版权阈值">
          <el-slider v-model="editForm.copyright_threshold" :min="0" :max="1" :step="0.05" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUpdate" :loading="updating">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { Monitor, Download, Edit, Delete, Loading, Checked } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()
const novel = ref<any>(null)

const editDialogVisible = ref(false)
const updating = ref(false)
const regenerating = ref(false)
const editForm = ref({
  style: '',
  world_setting: '',
  copyright_threshold: 0.2,
})

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await loadNovel()
  startPollingIfNeeded()
})

onUnmounted(() => {
  stopPolling()
})

async function loadNovel() {
  novel.value = await novelStore.fetchNovelDetail(route.params.id as string)
}

function startPollingIfNeeded() {
  stopPolling()
  if (novel.value?.outline_status === 'pending' || novel.value?.outline_status === 'generating') {
    pollTimer = setInterval(async () => {
      await loadNovel()
      if (novel.value?.outline_status !== 'pending' && novel.value?.outline_status !== 'generating') {
        stopPolling()
        if (novel.value?.outline_status === 'review') {
          ElMessage.success('大纲生成完成，请审核')
        } else if (novel.value?.outline_status === 'completed') {
          ElMessage.success('大纲生成完成')
        }
      }
    }, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function showEditDialog() {
  editForm.value = {
    style: novel.value.style || '',
    world_setting: novel.value.world_setting || '',
    copyright_threshold: novel.value.copyright_threshold || 0.2,
  }
  editDialogVisible.value = true
}

async function handleUpdate() {
  updating.value = true
  try {
    await novelStore.updateNovel(novel.value.project_id, editForm.value)
    ElMessage.success('项目已更新')
    editDialogVisible.value = false
    await loadNovel()
    startPollingIfNeeded()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  } finally {
    updating.value = false
  }
}

async function handleRegenerate() {
  regenerating.value = true
  try {
    await novelStore.regenerateOutline(novel.value.project_id)
    novel.value.outline_status = 'pending'
    startPollingIfNeeded()
    ElMessage.success('大纲重新生成已启动')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '重新生成失败')
  } finally {
    regenerating.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个项目吗？删除后无法恢复。',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await novelStore.deleteNovel(novel.value.project_id)
    ElMessage.success('项目已删除')
    router.push('/')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const statusMap: Record<string, { type: string; text: string }> = {
  draft: { type: 'info', text: '草稿' },
  writing: { type: 'warning', text: '创作中' },
  paused: { type: 'info', text: '已暂停' },
  completed: { type: 'success', text: '已完成' },
}
const roleLabels: Record<string, string> = { protagonist: '主角', antagonist: '反派', supporting: '配角' }
const progressColors = [
  { color: '#165DFF', percentage: 50 },
  { color: '#FF7D00', percentage: 80 },
  { color: '#00B42A', percentage: 100 },
]

function roleTagType(type: string) {
  return { protagonist: 'danger', antagonist: 'warning', supporting: 'info' }[type] || 'info'
}
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: var(--space-lg);
  align-items: start;
}

.header-actions {
  display: flex;
  gap: var(--space-sm);
}

.world-text {
  color: var(--color-text-regular);
  line-height: 1.8;
  white-space: pre-wrap;
}

.outline-content {
  color: var(--color-text-regular);
  line-height: 1.8;
  white-space: pre-wrap;
  font-size: var(--font-size-sm);
}

.volume-item {
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--color-border-light);
}

.volume-item h4 {
  color: var(--color-primary);
  margin-bottom: var(--space-xs);
}

.volume-item p {
  color: var(--color-text-regular);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}

.character-item {
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--color-border-light);
}

.character-item:last-child {
  border-bottom: none;
}

.character-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 4px;
}

.character-name {
  font-weight: 600;
  color: var(--color-text-primary);
}

.character-personality {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.character-background {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.progress-center {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.progress-pct {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.progress-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.outline-generating {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-xl) 0;
  color: var(--color-text-secondary);
}

.generating-spin {
  animation: spin 1.2s linear infinite;
  color: var(--color-primary);
}

.generating-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
