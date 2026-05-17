<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-logo">
          <div class="logo-mark">
            <el-icon :size="40"><EditPen /></el-icon>
          </div>
          <h1>AI 长篇小说<br/>自动生成系统</h1>
        </div>
        <p class="brand-desc">
          基于 LangGraph 6Agent 闭环协作，支持 10 万字级长篇小说全自动创作。
          大纲约束 · 滚动摘要 · 语义记忆 · 版权合规。
        </p>
        <div class="brand-features">
          <div class="feature-item">
            <el-icon :size="20"><Cpu /></el-icon>
            <span>6 大智能体协作</span>
          </div>
          <div class="feature-item">
            <el-icon :size="20"><Document /></el-icon>
            <span>10 万字长篇支持</span>
          </div>
          <div class="feature-item">
            <el-icon :size="20"><Shield /></el-icon>
            <span>版权合规校验</span>
          </div>
        </div>
      </div>
      <!-- 装饰图形 -->
      <div class="brand-decor">
        <div class="decor-circle c1"></div>
        <div class="decor-circle c2"></div>
        <div class="decor-circle c3"></div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="login-form-area">
      <div class="form-wrapper">
        <div class="form-header">
          <h2>欢迎使用</h2>
          <p>请登录或注册您的账户</p>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs">
          <el-tab-pane label="登录" name="login">
            <el-form @submit.prevent="handleLogin" label-position="top" size="large">
              <el-form-item label="用户名">
                <el-input
                  v-model="loginForm.username"
                  placeholder="请输入用户名"
                  :prefix-icon="User"
                />
              </el-form-item>
              <el-form-item label="密码">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  placeholder="请输入密码"
                  :prefix-icon="Lock"
                  show-password
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  native-type="submit"
                  :loading="loading"
                  class="submit-btn"
                >
                  登录
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form @submit.prevent="handleRegister" label-position="top" size="large">
              <el-form-item label="用户名">
                <el-input
                  v-model="registerForm.username"
                  placeholder="3-20 个字符"
                  :prefix-icon="User"
                />
              </el-form-item>
              <el-form-item label="密码">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  placeholder="6 位以上"
                  :prefix-icon="Lock"
                  show-password
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  native-type="submit"
                  :loading="loading"
                  class="submit-btn"
                >
                  注册
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, EditPen, Cpu, Document } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', password: '' })

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.username || !registerForm.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await authStore.register(registerForm.username, registerForm.password)
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
}

/* ── 左侧品牌区 ── */
.login-brand {
  flex: 1;
  background: linear-gradient(135deg, #0E42D2 0%, #165DFF 50%, #4080FF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 60px;
}

.brand-content {
  position: relative;
  z-index: 2;
  color: #fff;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.logo-mark {
  width: 64px;
  height: 64px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
}

.brand-logo h1 {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.5px;
}

.brand-desc {
  font-size: 15px;
  line-height: 1.8;
  opacity: 0.85;
  margin-bottom: 48px;
  max-width: 400px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  opacity: 0.9;
  background: rgba(255, 255, 255, 0.1);
  padding: 12px 16px;
  border-radius: 8px;
  backdrop-filter: blur(5px);
}

/* 装饰圆 */
.brand-decor {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.decor-circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
}

.c1 {
  width: 400px;
  height: 400px;
  top: -100px;
  right: -100px;
}

.c2 {
  width: 300px;
  height: 300px;
  bottom: -50px;
  left: -80px;
}

.c3 {
  width: 200px;
  height: 200px;
  top: 50%;
  right: 20%;
  background: rgba(255, 255, 255, 0.03);
}

/* ── 右侧表单区 ── */
.login-form-area {
  width: 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  padding: 60px;
}

.form-wrapper {
  width: 100%;
  max-width: 360px;
}

.form-header {
  margin-bottom: 40px;
}

.form-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #1D2129;
  margin-bottom: 8px;
}

.form-header p {
  font-size: 14px;
  color: #86909C;
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 32px;
}

.login-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 500;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
}
</style>
