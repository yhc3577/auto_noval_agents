<template>
  <div class="app-layout">
    <!-- 左侧边栏 -->
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-logo" @click="router.push('/')">
        <div class="logo-icon">
          <el-icon :size="24"><EditPen /></el-icon>
        </div>
        <transition name="fade">
          <span v-show="!sidebarCollapsed" class="logo-text">AI 小说系统</span>
        </transition>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="sidebarCollapsed"
        class="sidebar-menu"
        router
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>项目列表</template>
        </el-menu-item>

        <el-menu-item index="/create">
          <el-icon><Plus /></el-icon>
          <template #title>新建小说</template>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>

        <el-menu-item index="/settings/prompts">
          <el-icon><ChatDotSquare /></el-icon>
          <template #title>Prompt 管理</template>
        </el-menu-item>

        <template v-if="currentNovelId">
          <el-menu-item-group>
            <template #title>
              <span v-show="!sidebarCollapsed" class="group-title">当前项目</span>
            </template>
            <el-menu-item :index="`/novel/${currentNovelId}`">
              <el-icon><Document /></el-icon>
              <template #title>项目详情</template>
            </el-menu-item>
            <el-menu-item :index="`/novel/${currentNovelId}/review`">
              <el-icon><Checked /></el-icon>
              <template #title>大纲审核</template>
            </el-menu-item>
            <el-menu-item :index="`/novel/${currentNovelId}/console`">
              <el-icon><Monitor /></el-icon>
              <template #title>创作控制台</template>
            </el-menu-item>
            <el-menu-item :index="`/novel/${currentNovelId}/export`">
              <el-icon><Download /></el-icon>
              <template #title>导出设置</template>
            </el-menu-item>
          </el-menu-item-group>
        </template>
      </el-menu>

      <div class="sidebar-footer">
        <el-button
          :icon="sidebarCollapsed ? 'DArrowRight' : 'DArrowLeft'"
          text
          @click="sidebarCollapsed = !sidebarCollapsed"
        />
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="app-main-wrapper">
      <!-- 顶部导航栏 -->
      <header class="app-topbar">
        <div class="topbar-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">
              {{ route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <el-tooltip :content="isDark ? '浅色模式' : '暗黑模式'" placement="bottom">
            <el-button :icon="isDark ? 'Sunny' : 'Moon'" text circle @click="toggleDark" />
          </el-tooltip>
          <el-dropdown trigger="click" @command="handleCommand">
            <div class="user-avatar">
              <el-avatar :size="32" style="background: var(--color-primary)">
                {{ username.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 主内容区 -->
      <main class="app-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  EditPen, HomeFilled, Plus, Document, Monitor, Download, Checked,
  ArrowDown, SwitchButton, Setting, ChatDotSquare
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const sidebarCollapsed = ref(false)
const isDark = ref(false)
const username = computed(() => authStore.username || '用户')

const currentNovelId = computed(() => {
  const id = route.params.id as string
  return id || null
})

const activeMenu = computed(() => route.path)

function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
}

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* ── 侧边栏 ── */
.app-sidebar {
  width: var(--sidebar-width);
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-normal);
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-logo {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  padding: 0 var(--space-md);
  gap: var(--space-sm);
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.logo-text {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--color-text-primary);
  white-space: nowrap;
  letter-spacing: -0.5px;
}

.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding-top: var(--space-sm);
}

.sidebar-menu .el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: var(--radius-md);
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--color-primary-lighter) !important;
  color: var(--color-primary) !important;
  font-weight: 500;
}

.group-title {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-footer {
  padding: var(--space-sm);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  justify-content: center;
}

/* ── 主区域 ── */
.app-main-wrapper {
  flex: 1;
  margin-left: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  transition: margin-left var(--transition-normal);
}

.collapsed + .app-main-wrapper,
.app-sidebar.collapsed ~ .app-main-wrapper {
  margin-left: var(--sidebar-collapsed-width);
}

/* ── 顶栏 ── */
.app-topbar {
  height: var(--topbar-height);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-lg);
  position: sticky;
  top: 0;
  z-index: 90;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.user-avatar {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.user-avatar:hover {
  background: var(--color-bg-page);
}

.username {
  font-size: var(--font-size-md);
  color: var(--color-text-regular);
  font-weight: 500;
}

/* ── 内容区 ── */
.app-content {
  flex: 1;
  overflow-y: auto;
}

/* ── 过渡动画 ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
