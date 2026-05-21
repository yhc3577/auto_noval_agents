<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Prompt 管理</h1>
      <p class="page-desc">管理各 Agent 的系统提示词和用户提示词模板，支持自定义覆盖和重置默认值</p>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 主内容 -->
    <div v-else class="prompt-layout">
      <!-- 顶部：Agent 类型标签页 -->
      <el-tabs v-model="activeAgent" @tab-change="onAgentChange" type="card">
        <el-tab-pane
          v-for="agent in agentTypes"
          :key="agent.value"
          :label="agent.label"
          :name="agent.value"
        />
      </el-tabs>

      <!-- 操作栏 -->
      <div class="toolbar">
        <span class="prompt-count">共 {{ filteredItems.length }} 个模板</span>
        <el-button type="warning" :icon="RefreshRight" plain @click="handleResetAll">
          全部重置为默认
        </el-button>
      </div>

      <!-- Prompt 列表 -->
      <div v-if="filteredItems.length === 0" class="empty-state">
        <p class="empty-text">该 Agent 类型暂无模板</p>
      </div>

      <div v-else class="prompt-list">
        <div
          v-for="item in filteredItems"
          :key="item.prompt_key"
          class="prompt-card"
          :class="{ 'is-customized': item.is_customized }"
        >
          <div class="prompt-card-header">
            <div class="prompt-info">
              <div class="prompt-name-row">
                <span class="prompt-name">{{ item.name }}</span>
                <el-tag v-if="item.is_customized" type="success" size="small" effect="light">
                  已自定义
                </el-tag>
                <el-tag v-else size="small" type="info" effect="light">默认</el-tag>
              </div>
              <div class="prompt-meta">
                <el-tag size="small" effect="plain">{{ item.prompt_type === 'system' ? 'System' : 'User' }}</el-tag>
                <span class="prompt-desc">{{ item.description }}</span>
              </div>
              <div v-if="item.variables.length > 0" class="prompt-vars">
                <span class="vars-label">可用变量：</span>
                <el-tag
                  v-for="v in item.variables"
                  :key="v"
                  size="small"
                  class="var-tag"
                  @click="insertVar(item, v)"
                >
                  {{ '{' + v + '}' }}
                </el-tag>
              </div>
            </div>
            <div class="prompt-actions">
              <el-button size="small" :icon="Edit" @click="openEditDialog(item)">
                编辑
              </el-button>
              <el-button
                v-if="item.is_customized"
                size="small"
                :icon="RefreshRight"
                plain
                type="warning"
                @click="handleReset(item)"
              >
                恢复默认
              </el-button>
            </div>
          </div>

          <!-- 内容预览（可折叠） -->
          <div class="prompt-preview" :class="{ 'is-expanded': expandedKeys.has(item.prompt_key) }">
            <div class="preview-toggle" @click="toggleExpand(item.prompt_key)">
              <pre class="preview-text">{{ expandedKeys.has(item.prompt_key) ? item.current_content : (item.current_content.slice(0, 120) + '...') }}</pre>
              <div class="toggle-bar">
                <el-icon class="toggle-icon" :class="{ rotated: expandedKeys.has(item.prompt_key) }">
                  <ArrowDown />
                </el-icon>
                <span class="toggle-label">{{ expandedKeys.has(item.prompt_key) ? '收起' : `展开全部（${item.current_content.length} 字符）` }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingItem ? `编辑：${editingItem.name}` : ''"
      width="800px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="edit-layout">
        <div class="edit-vars" v-if="editingItem && editingItem.variables.length > 0">
          <span class="vars-label">点击变量插入到光标位置：</span>
          <div class="vars-list">
            <el-tag
              v-for="v in editingItem.variables"
              :key="v"
              size="small"
              class="var-tag clickable"
              @click="insertVar(editingItem, v)"
            >
              {{ '{' + v + '}' }}
            </el-tag>
          </div>
        </div>
        <el-input
          ref="editInputRef"
          v-model="editContent"
          type="textarea"
          :rows="20"
          placeholder="编辑模板内容..."
        />
        <div class="default-toggle">
          <el-popconfirm
            title="确定要恢复为默认模板吗？当前编辑内容将丢失。"
            @confirm="editContent = editingItem?.default_content || ''"
          >
            <template #reference>
              <el-button text type="primary" size="small">重新加载默认模板</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePromptStore, type PromptTemplate } from '@/stores/prompt'
import { ElMessage, ElMessageBox, type InputInstance } from 'element-plus'
import { Loading, Edit, RefreshRight, ArrowDown } from '@element-plus/icons-vue'

const promptStore = usePromptStore()
const loading = ref(true)
const activeAgent = ref('writer')
const dialogVisible = ref(false)
const editingItem = ref<PromptTemplate | null>(null)
const editContent = ref('')
const saving = ref(false)
const editInputRef = ref<InputInstance>()
const expandedKeys = ref<Set<string>>(new Set())

const agentTypes = [
  { value: 'writer', label: '写作Agent' },
  { value: 'auditor', label: '审核Agent' },
  { value: 'summarizer', label: '摘要Agent' },
  { value: 'planner', label: '规划Agent' },
  { value: 'pipeline', label: '流水线(Trim/Expand)' },
  { value: 'chapter_api', label: '章节API' },
]

const filteredItems = computed(() =>
  promptStore.items.filter(i => i.agent_type === activeAgent.value)
)

onMounted(async () => {
  await promptStore.fetchList()
  loading.value = false
})

function onAgentChange() {
  // 切换 agent 时展开状态不变
}

function toggleExpand(key: string) {
  if (expandedKeys.value.has(key)) {
    expandedKeys.value.delete(key)
  } else {
    expandedKeys.value.add(key)
  }
  // 触发响应式更新
  expandedKeys.value = new Set(expandedKeys.value)
}

function openEditDialog(item: PromptTemplate) {
  editingItem.value = item
  editContent.value = item.current_content
  dialogVisible.value = true
}

function insertVar(_item: PromptTemplate, v: string) {
  const varText = '{' + v + '}'
  // 如果是编辑对话框中的变量点击，插入到 textarea 光标位置
  if (dialogVisible.value && editInputRef.value) {
    const textarea = (editInputRef.value as any).textarea as HTMLTextAreaElement | undefined
    if (textarea) {
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      editContent.value =
        editContent.value.slice(0, start) + varText + editContent.value.slice(end)
      // 恢复焦点和光标
      setTimeout(() => {
        textarea.focus()
        const pos = start + varText.length
        textarea.setSelectionRange(pos, pos)
      }, 100)
      return
    }
  }
  // 非编辑模式：复制到剪贴板
  navigator.clipboard.writeText(varText)
  ElMessage.success(`变量 ${varText} 已复制到剪贴板`)
}

async function handleSave() {
  if (!editingItem.value) return
  saving.value = true
  try {
    await promptStore.updatePrompt(editingItem.value.prompt_key, editContent.value)
    ElMessage.success('模板已更新')
    dialogVisible.value = false
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '保存失败'
    ElMessage.error(detail)
  } finally {
    saving.value = false
  }
}

async function handleReset(item: PromptTemplate) {
  try {
    await ElMessageBox.confirm(
      `确定要将 "${item.name}" 恢复为默认模板吗？当前自定义内容将丢失。`,
      '确认恢复默认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await promptStore.resetPrompt(item.prompt_key)
    ElMessage.success('已恢复默认值')
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '重置失败'
    ElMessage.error(detail)
  }
}

async function handleResetAll() {
  try {
    await ElMessageBox.confirm(
      '确定要将所有 Prompt 模板恢复为默认值吗？所有自定义内容将丢失。此操作不可撤销。',
      '确认全部重置',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const result = await promptStore.resetAll()
    ElMessage.success(result.message || '全部已重置')
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '重置失败'
    ElMessage.error(detail)
  }
}
</script>

<style scoped>
.prompt-layout {
  max-width: 1000px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-lg);
}

.prompt-count {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* ── Prompt 卡片 ── */
.prompt-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.prompt-card {
  border: 2px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  transition: all var(--transition-normal);
}

.prompt-card:hover {
  border-color: var(--color-primary-lighter);
}

.prompt-card.is-customized {
  border-color: var(--color-success);
  background: var(--color-success-lighter, #f0faf0);
}

.prompt-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-md);
}

.prompt-info {
  flex: 1;
  min-width: 0;
}

.prompt-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}

.prompt-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

.prompt-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.prompt-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.prompt-vars {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-wrap: wrap;
}

.vars-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.var-tag {
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.var-tag:hover {
  opacity: 0.8;
}

.prompt-actions {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-shrink: 0;
}

/* ── 预览（可折叠） ── */
.prompt-preview {
  margin-top: var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  overflow: hidden;
}

.preview-toggle {
  cursor: pointer;
}

.preview-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-regular);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  margin: 0;
  padding: var(--space-md);
  font-family: var(--font-mono);
}

.prompt-preview:not(.is-expanded) .preview-text {
  max-height: 72px;
  overflow: hidden;
}

.prompt-preview.is-expanded .preview-text {
  max-height: none;
}

.toggle-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-md) var(--space-sm);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  border-top: 1px solid var(--color-border-lighter, #ebeef5);
  transition: color var(--transition-fast);
}

.toggle-bar:hover {
  color: var(--color-primary);
}

.toggle-icon {
  transition: transform var(--transition-fast);
  font-size: 12px;
}

.toggle-icon.rotated {
  transform: rotate(180deg);
}

.toggle-label {
  font-size: var(--font-size-xs);
}

/* ── 编辑对话框 ── */
.edit-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.edit-vars {
  padding: var(--space-sm) var(--space-md);
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.vars-list {
  display: flex;
  gap: var(--space-xs);
  flex-wrap: wrap;
  margin-top: var(--space-xs);
}

.var-tag.clickable {
  cursor: pointer;
  transition: all var(--transition-fast);
}

.var-tag.clickable:hover {
  background: var(--color-primary);
  color: #fff;
}

.default-toggle {
  display: flex;
  justify-content: flex-end;
}

/* ── 公共 ── */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-2xl) 0;
  gap: var(--space-sm);
  color: var(--color-text-secondary);
}

.empty-text {
  font-size: var(--font-size-md);
  color: var(--color-text-placeholder);
}
</style>
