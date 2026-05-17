<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">我的小说项目</h1>
      <el-button type="primary" :icon="Plus" size="large" @click="router.push('/create')">
        新建小说
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row" v-if="novelStore.novels.length > 0">
      <div class="stat-card">
        <div class="stat-card__label">总项目数</div>
        <div class="stat-card__value">{{ novelStore.novels.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">创作中</div>
        <div class="stat-card__value" style="color: var(--color-warning)">
          {{ novelStore.novels.filter(n => n.status === 'writing').length }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">已完成</div>
        <div class="stat-card__value" style="color: var(--color-success)">
          {{ novelStore.novels.filter(n => n.status === 'completed').length }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__label">总章节</div>
        <div class="stat-card__value">
          {{ novelStore.novels.reduce((s, n) => s + n.chapter_count, 0) }}
        </div>
      </div>
    </div>

    <!-- 项目卡片网格 -->
    <div class="card-grid" v-if="novelStore.novels.length > 0">
      <div
        v-for="novel in novelStore.novels"
        :key="novel.project_id"
        class="novel-card"
        @click="router.push(`/novel/${novel.project_id}`)"
      >
        <div class="novel-card__header">
          <h3 class="novel-card__title">{{ novel.title }}</h3>
          <el-tag :type="statusMap[novel.status]?.type" size="small" effect="light">
            {{ statusMap[novel.status]?.text }}
          </el-tag>
        </div>

        <div class="novel-card__meta">
          <span class="meta-item">
            <el-icon><Collection /></el-icon>{{ novel.genre }}
          </span>
          <span class="meta-item">
            <el-icon><Document /></el-icon>{{ novel.chapter_count }} 章
          </span>
        </div>

        <div class="novel-card__progress">
          <div class="progress-info">
            <span>创作进度</span>
            <span class="progress-num">{{ novel.current_chapter }}/{{ novel.chapter_count }}</span>
          </div>
          <el-progress
            :percentage="Math.round((novel.current_chapter / novel.chapter_count) * 100)"
            :stroke-width="8"
            :show-text="false"
            :color="novel.status === 'completed' ? 'var(--color-success)' : 'var(--color-primary)'"
          />
        </div>

        <div class="novel-card__footer">
          <span class="time">{{ formatDate(novel.created_at) }}</span>
          <el-button text type="primary" size="small" @click.stop="router.push(`/novel/${novel.project_id}/console`)">
            进入控制台 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-else>
      <el-empty description="还没有小说项目">
        <el-button type="primary" size="large" @click="router.push('/create')">
          创建第一部小说
        </el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { Plus, Collection, Document, ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const novelStore = useNovelStore()

onMounted(() => novelStore.fetchNovels())

const statusMap: Record<string, { type: string; text: string }> = {
  draft: { type: 'info', text: '草稿' },
  writing: { type: 'warning', text: '创作中' },
  paused: { type: 'info', text: '已暂停' },
  completed: { type: 'success', text: '已完成' },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.novel-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  cursor: pointer;
  transition: all var(--transition-normal);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.novel-card:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-lighter);
  transform: translateY(-2px);
}

.novel-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.novel-card__title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.novel-card__meta {
  display: flex;
  gap: var(--space-lg);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.novel-card__progress {
  margin-top: auto;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-xs);
}

.progress-num {
  font-weight: 600;
  color: var(--color-primary);
}

.novel-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--space-sm);
  border-top: 1px solid var(--color-border-light);
}

.time {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}

.empty-state {
  display: flex;
  justify-content: center;
  padding-top: 120px;
}
</style>
