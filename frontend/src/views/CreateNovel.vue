<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">新建小说</h1>
    </div>

    <div class="create-layout">
      <!-- 左侧表单 -->
      <div class="create-form-area">
        <!-- 基本信息 -->
        <div class="section-card">
          <div class="section-title">基本信息</div>
          <el-form :model="form" label-position="top" size="large">
            <el-form-item label="小说标题" required>
              <el-input v-model="form.title" placeholder="给你的小说起个名字" maxlength="50" show-word-limit />
            </el-form-item>
            <el-form-item label="大纲方式">
              <el-radio-group v-model="outlineMode">
                <el-radio-button value="generate">AI 生成大纲</el-radio-button>
                <el-radio-button value="import">使用已有大纲</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="题材" required>
                  <el-select v-model="form.genre" placeholder="选择或输入题材" filterable allow-create style="width: 100%">
                    <el-option v-for="g in genres" :key="g" :label="g" :value="g" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="文风" required>
                  <el-select v-model="form.style" placeholder="选择或输入文风" filterable allow-create style="width: 100%">
                    <el-option v-for="s in styles" :key="s" :label="s" :value="s" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="版权查重阈值">
                  <el-slider v-model="copyrightThreshold" :min="5" :max="40" :step="5" :format-tooltip="(v: number) => `${v}%`" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <!-- 世界观设定 -->
        <div class="section-card">
          <div class="section-title">世界观设定</div>
          <el-input
            v-model="form.world_setting"
            type="textarea"
            :rows="5"
            placeholder="描述小说的世界观、势力体系、战力规则、核心冲突..."
            maxlength="2000"
            show-word-limit
          />
        </div>

        <!-- 已有大纲输入 -->
        <div class="section-card" v-if="outlineMode === 'import'">
          <div class="section-title">粘贴大纲</div>
          <el-input
            v-model="existingOutline"
            type="textarea"
            :rows="15"
            placeholder="粘贴你的小说大纲，系统会自动解析题材、文风、章节数等信息..."
          />
          <div class="config-hint">系统将自动从大纲中提取题材、文风、章节数等配置信息</div>
        </div>

        <!-- 章节配置 -->
        <div class="section-card" v-if="outlineMode === 'generate'">
          <div class="section-title">章节配置</div>
          <el-row :gutter="24">
            <el-col :span="12">
              <el-form-item label="总章节数">
                <el-input-number v-model="form.chapter_count" :min="50" :max="500" :step="10" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="每章目标字数">
                <el-input-number v-model="form.words_per_chapter" :min="2000" :max="5000" :step="500" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <div class="config-hint">
            预计总字数：<strong>{{ ((form.chapter_count * form.words_per_chapter) / 10000).toFixed(1) }} 万字</strong>
          </div>
        </div>

        <!-- 角色设定 -->
        <div class="section-card" v-if="outlineMode === 'generate'">
          <div class="section-title">
            角色设定
            <el-button type="primary" text :icon="Plus" @click="addCharacter" style="margin-left: auto">
              添加角色
            </el-button>
          </div>

          <div v-for="(char, index) in form.characters" :key="index" class="character-card">
            <div class="character-card__header">
              <span class="character-index">#{{ index + 1 }}</span>
              <el-tag :type="roleTagType(char.role_type)" size="small" effect="plain">
                {{ roleLabels[char.role_type] }}
              </el-tag>
              <el-button
                v-if="form.characters.length > 1"
                text
                type="danger"
                size="small"
                :icon="Delete"
                @click="form.characters.splice(index, 1)"
              />
            </div>
            <el-row :gutter="12">
              <el-col :span="6">
                <el-input v-model="char.name" placeholder="角色名" />
              </el-col>
              <el-col :span="6">
                <el-select v-model="char.role_type" placeholder="角色类型" style="width: 100%">
                  <el-option label="主角" value="protagonist" />
                  <el-option label="反派" value="antagonist" />
                  <el-option label="配角" value="supporting" />
                </el-select>
              </el-col>
              <el-col :span="6">
                <el-input v-model="char.personality" placeholder="性格特征" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="char.background" placeholder="身世背景" />
              </el-col>
            </el-row>
          </div>
        </div>
      </div>

      <!-- 右侧预览 -->
      <div class="create-preview">
        <div class="section-card sticky-card">
          <div class="section-title">配置预览</div>
          <div class="preview-item">
            <span class="preview-label">标题</span>
            <span class="preview-value">{{ form.title || '未填写' }}</span>
          </div>
          <div class="preview-item">
            <span class="preview-label">题材</span>
            <span class="preview-value">{{ form.genre }}</span>
          </div>
          <div class="preview-item">
            <span class="preview-label">文风</span>
            <span class="preview-value">{{ form.style }}</span>
          </div>
          <div class="preview-item">
            <span class="preview-label">规模</span>
            <span class="preview-value">{{ form.chapter_count }} 章 / {{ form.words_per_chapter }} 字/章</span>
          </div>
          <div class="preview-item">
            <span class="preview-label">角色</span>
            <span class="preview-value">{{ form.characters.filter(c => c.name).map(c => c.name).join('、') || '未填写' }}</span>
          </div>
          <div class="preview-item">
            <span class="preview-label">查重阈值</span>
            <span class="preview-value">{{ copyrightThreshold }}%</span>
          </div>

          <el-divider />

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleCreate"
            style="width: 100%"
          >
            {{ outlineMode === 'import' ? '创建项目并导入大纲' : '创建项目并生成大纲' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'

const router = useRouter()
const novelStore = useNovelStore()
const loading = ref(false)
const copyrightThreshold = ref(20)
const outlineMode = ref<'generate' | 'import'>('generate')
const existingOutline = ref('')

const genres = ['玄幻', '都市', '科幻', '仙侠', '历史', '悬疑', '言情', '武侠']
const styles = ['热血', '轻松', '严肃', '幽默', '暗黑', '沉稳', '唯美']
const roleLabels: Record<string, string> = { protagonist: '主角', antagonist: '反派', supporting: '配角' }

const form = reactive({
  title: '',
  genre: '玄幻',
  style: '热血',
  world_setting: '',
  chapter_count: 100,
  words_per_chapter: 3000,
  characters: [
    { name: '', role_type: 'protagonist', personality: '', background: '', relationships: [] }
  ]
})

function addCharacter() {
  form.characters.push({ name: '', role_type: 'supporting', personality: '', background: '', relationships: [] })
}

function roleTagType(type: string) {
  return { protagonist: 'danger', antagonist: 'warning', supporting: 'info' }[type] || 'info'
}

async function handleCreate() {
  if (!form.title) {
    ElMessage.warning('请填写标题')
    return
  }
  if (outlineMode.value === 'import') {
    if (!existingOutline.value.trim()) {
      ElMessage.warning('请粘贴大纲内容')
      return
    }
  } else {
    if (!form.world_setting) {
      ElMessage.warning('请填写世界观设定')
      return
    }
  }
  loading.value = true
  try {
    const payload: any = { ...form }
    if (outlineMode.value === 'import') {
      payload.existing_outline = existingOutline.value
    }
    const result = await novelStore.createNovel(payload)
    ElMessage.success(outlineMode.value === 'import' ? '项目创建成功，大纲已导入' : '项目创建成功，大纲生成中...')
    router.push(`/novel/${result.project_id}`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.create-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--space-lg);
  align-items: start;
}

.section-card + .section-card {
  margin-top: var(--space-md);
}

.character-card {
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  margin-bottom: var(--space-sm);
}

.character-card__header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.character-index {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  font-weight: 600;
}

.config-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-sm);
}

.config-hint strong {
  color: var(--color-primary);
}

.sticky-card {
  position: sticky;
  top: calc(var(--topbar-height) + var(--space-lg));
}

.preview-item {
  display: flex;
  justify-content: space-between;
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--color-border-light);
}

.preview-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.preview-value {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  font-weight: 500;
  text-align: right;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
