<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">导出与设置</h1>
    </div>

    <div class="export-layout">
      <!-- 导出功能 -->
      <div class="section-card">
        <div class="section-title">全书导出</div>
        <p class="section-desc">将已完成的章节导出为完整小说文件</p>

        <div class="export-options">
          <div
            class="export-option"
            :class="{ active: format === 'txt' }"
            @click="format = 'txt'"
          >
            <div class="option-icon" style="background: #E8F3FF; color: #165DFF">
              <el-icon :size="28"><Document /></el-icon>
            </div>
            <div class="option-info">
              <h4>TXT 纯文本</h4>
              <p>通用格式，兼容所有阅读器</p>
            </div>
            <el-radio v-model="format" value="txt" />
          </div>

          <div
            class="export-option"
            :class="{ active: format === 'markdown' }"
            @click="format = 'markdown'"
          >
            <div class="option-icon" style="background: #E8FFEA; color: #00B42A">
              <el-icon :size="28"><Notebook /></el-icon>
            </div>
            <div class="option-info">
              <h4>Markdown</h4>
              <p>保留格式标记，适合在线发布</p>
            </div>
            <el-radio v-model="format" value="markdown" />
          </div>
        </div>

        <el-button
          type="primary"
          size="large"
          :icon="Download"
          :loading="loading"
          @click="handleExport"
          style="margin-top: var(--space-lg)"
        >
          导出下载
        </el-button>
      </div>

      <!-- 系统设置 -->
      <div class="section-card">
        <div class="section-title">版权设置</div>
        <el-form label-position="top" size="large">
          <el-form-item label="版权查重阈值">
            <el-slider
              v-model="copyrightThreshold"
              :min="5"
              :max="40"
              :step="5"
              :format-tooltip="(v: number) => `${v}%`"
              show-stops
            />
            <div class="threshold-hint">
              值越低越严格，当前阈值：<strong>{{ copyrightThreshold }}%</strong>
            </div>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleSaveSettings">保存设置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 项目信息 -->
      <div class="section-card" v-if="novel">
        <div class="section-title">项目信息</div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目名称">{{ novel.title }}</el-descriptions-item>
          <el-descriptions-item label="题材">{{ novel.genre }}</el-descriptions-item>
          <el-descriptions-item label="文风">{{ novel.style }}</el-descriptions-item>
          <el-descriptions-item label="总章节">{{ novel.chapter_count }}</el-descriptions-item>
          <el-descriptions-item label="已完成">{{ novel.current_chapter }} 章</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusMap[novel.status]?.type" effect="light">
              {{ statusMap[novel.status]?.text }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import api from '@/services/api'
import { ElMessage } from 'element-plus'
import { Document, Notebook, Download } from '@element-plus/icons-vue'

const route = useRoute()
const novelStore = useNovelStore()
const format = ref('txt')
const loading = ref(false)
const copyrightThreshold = ref(20)
const novel = ref<any>(null)

const projectId = route.params.id as string

const statusMap: Record<string, { type: string; text: string }> = {
  draft: { type: 'info', text: '草稿' },
  writing: { type: 'warning', text: '创作中' },
  paused: { type: 'info', text: '已暂停' },
  completed: { type: 'success', text: '已完成' },
}

onMounted(async () => {
  novel.value = await novelStore.fetchNovelDetail(projectId)
  if (novel.value?.copyright_threshold) {
    copyrightThreshold.value = Math.round(novel.value.copyright_threshold * 100)
  }
})

async function handleExport() {
  loading.value = true
  try {
    const response = await api.get('/novel/export', {
      params: { project_id: projectId, format: format.value },
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${novel.value?.title || 'novel'}.${format.value === 'txt' ? 'txt' : 'md'}`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    loading.value = false
  }
}

async function handleSaveSettings() {
  try {
    await novelStore.updateNovel(projectId, { copyright_threshold: copyrightThreshold.value / 100 })
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
.export-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  max-width: 800px;
}

.section-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-lg);
}

.export-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-md);
}

.export-option {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-lg);
  border: 2px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.export-option:hover {
  border-color: var(--color-primary-lighter);
}

.export-option.active {
  border-color: var(--color-primary);
  background: var(--color-primary-lighter);
}

.option-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-info h4 {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}

.option-info p {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.threshold-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-xs);
}

.threshold-hint strong {
  color: var(--color-primary);
}
</style>
