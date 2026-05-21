<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">系统设置</h1>
    </div>

    <div class="settings-layout">
      <!-- 模型配置 -->
      <div class="section-card">
        <div class="section-title">模型配置</div>
        <p class="section-desc">配置 AI 大语言模型，支持切换不同服务商和模型</p>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>加载中...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="configs.length === 0" class="empty-state">
          <div class="empty-icon">
            <el-icon :size="48"><Setting /></el-icon>
          </div>
          <p class="empty-text">暂无模型配置</p>
          <p class="empty-hint">添加模型配置后，系统将使用您指定的 API 进行 AI 创作</p>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">
            添加模型配置
          </el-button>
        </div>

        <!-- 配置列表 -->
        <div v-else class="config-list">
          <div class="config-list-header">
            <span class="config-count">共 {{ configs.length }} 个配置</span>
            <el-button type="primary" :icon="Plus" @click="openAddDialog">
              添加模型配置
            </el-button>
          </div>

          <div
            v-for="config in configs"
            :key="config.config_id"
            class="config-card"
            :class="{ 'is-active': config.is_active }"
          >
            <div class="config-main">
              <div class="config-info">
                <div class="config-name-row">
                  <span class="config-name">{{ config.name }}</span>
                  <el-tag v-if="config.is_active" type="success" size="small" effect="light">
                    使用中
                  </el-tag>
                </div>
                <div class="config-meta">
                  <el-tag size="small" effect="plain">{{ config.provider }}</el-tag>
                  <span class="config-model">{{ config.model }}</span>
                  <span class="config-key">{{ config.api_key_masked || '(未设置)' }}</span>
                </div>
              </div>

              <div class="config-actions">
                <el-button
                  v-if="!config.is_active"
                  type="primary"
                  size="small"
                  plain
                  :loading="activatingId === config.config_id"
                  @click="handleActivate(config.config_id)"
                >
                  设为默认
                </el-button>
                <el-button size="small" :icon="Edit" @click="openEditDialog(config)">
                  编辑
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :icon="Delete"
                  :disabled="config.is_active"
                  @click="handleDelete(config)"
                >
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 系统信息 -->
      <div class="section-card">
        <div class="section-title">关于</div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统名称">AI 长篇小说自动生成系统</el-descriptions-item>
          <el-descriptions-item label="版本">1.0.0</el-descriptions-item>
          <el-descriptions-item label="技术架构">LangGraph 6Agent + FastAPI + Vue 3</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑模型配置' : '添加模型配置'"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-position="top"
        size="large"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：我的 DeepSeek" maxlength="50" show-word-limit />
        </el-form-item>

        <el-form-item label="服务商" prop="provider">
          <el-select v-model="form.provider" placeholder="选择 LLM 服务商" style="width: 100%" @change="onProviderChange">
            <el-option
              v-for="p in providers"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="模型名称" prop="model">
          <el-input v-model="form.model" placeholder="例如：deepseek-chat" maxlength="100" />
          <div class="config-hint">服务商提供的模型标识符，用于 API 调用</div>
        </el-form-item>

        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            placeholder="输入 API Key"
            show-password
            maxlength="200"
          />
          <div class="config-hint">API Key 将加密存储在服务端，不会明文展示</div>
        </el-form-item>

        <el-form-item label="API 地址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="API 基础地址" maxlength="300" />
          <div class="config-hint">OpenAI 兼容格式的 API 地址，通常以 /v1 结尾</div>
        </el-form-item>

        <el-form-item label="最大输出 Token" prop="max_tokens">
          <el-input-number
            v-model="form.max_tokens"
            :min="256"
            :max="65536"
            :step="1024"
            style="width: 100%"
          />
          <div class="config-hint">单次生成的最大 token 数量，默认 8192</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '添加配置' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useModelConfigStore, type ModelConfig, type ProviderOption } from '@/stores/modelConfig'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Loading, Setting, Plus, Edit, Delete } from '@element-plus/icons-vue'

const modelConfigStore = useModelConfigStore()
const configs = ref<ModelConfig[]>([])
const loading = ref(true)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingConfigId = ref<string | null>(null)
const submitting = ref(false)
const activatingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const providers = ref<ProviderOption[]>([])

const form = reactive({
  name: '',
  provider: '',
  model: '',
  api_key: '',
  base_url: '',
  max_tokens: 8192,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请选择服务商', trigger: 'change' }],
  model: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
}

onMounted(async () => {
  await loadConfigs()
})

async function loadConfigs() {
  loading.value = true
  try {
    await modelConfigStore.fetchConfigs()
    configs.value = modelConfigStore.configs
    providers.value = modelConfigStore.availableProviders
  } catch {
    ElMessage.error('加载模型配置失败')
  } finally {
    loading.value = false
  }
}

function onProviderChange(value: string) {
  const provider = providers.value.find(p => p.value === value)
  if (provider && !form.base_url) {
    form.base_url = provider.default_base_url
  }
}

function openAddDialog() {
  isEditing.value = false
  editingConfigId.value = null
  form.name = ''
  form.provider = ''
  form.model = ''
  form.api_key = ''
  form.base_url = ''
  form.max_tokens = 8192
  dialogVisible.value = true
}

function openEditDialog(config: ModelConfig) {
  isEditing.value = true
  editingConfigId.value = config.config_id
  form.name = config.name
  form.provider = config.provider
  form.model = config.model
  form.api_key = ''
  form.base_url = config.base_url
  form.max_tokens = config.max_tokens || 8192
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEditing.value && editingConfigId.value) {
      const updates: Record<string, string | number> = {}
      updates.name = form.name
      updates.provider = form.provider
      updates.model = form.model
      if (form.api_key) updates.api_key = form.api_key
      updates.base_url = form.base_url
      updates.max_tokens = form.max_tokens
      await modelConfigStore.updateConfig(editingConfigId.value, updates)
      ElMessage.success('配置已更新')
    } else {
      await modelConfigStore.createConfig({ ...form })
      ElMessage.success('配置已添加')
    }
    dialogVisible.value = false
    await loadConfigs()
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '操作失败'
    ElMessage.error(detail)
  } finally {
    submitting.value = false
  }
}

async function handleActivate(configId: string) {
  activatingId.value = configId
  try {
    await modelConfigStore.activateConfig(configId)
    ElMessage.success('已切换模型配置')
    await loadConfigs()
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '切换失败'
    ElMessage.error(detail)
  } finally {
    activatingId.value = null
  }
}

async function handleDelete(config: ModelConfig) {
  try {
    await ElMessageBox.confirm(
      `确定要删除配置"${config.name}"吗？此操作不可撤销。`,
      '确认删除',
      { type: 'warning' }
    )
  } catch {
    return
  }

  try {
    await modelConfigStore.deleteConfig(config.config_id)
    ElMessage.success('配置已删除')
    await loadConfigs()
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '删除失败'
    ElMessage.error(detail)
  }
}
</script>

<style scoped>
.settings-layout {
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

/* ── 加载 / 空状态 ── */
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

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--color-bg-page);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-placeholder);
  margin-bottom: var(--space-sm);
}

.empty-text {
  font-size: var(--font-size-md);
  color: var(--color-text-regular);
  font-weight: 500;
}

.empty-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  max-width: 320px;
  text-align: center;
  margin-bottom: var(--space-md);
}

/* ── 配置列表 ── */
.config-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.config-count {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.config-card {
  border: 2px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  transition: all var(--transition-normal);
}

.config-card + .config-card {
  margin-top: var(--space-md);
}

.config-card:hover {
  border-color: var(--color-primary-lighter);
}

.config-card.is-active {
  border-color: var(--color-primary);
  background: var(--color-primary-lighter);
}

.config-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-md);
}

.config-info {
  flex: 1;
  min-width: 0;
}

.config-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}

.config-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

.config-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.config-model {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  font-family: var(--font-mono);
}

.config-key {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  font-family: var(--font-mono);
}

.config-actions {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-shrink: 0;
}

/* ── 提示文本 ── */
.config-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-xs);
}
</style>
