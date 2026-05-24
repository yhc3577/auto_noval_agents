import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
    },
    {
      path: '/',
      component: () => import('@/components/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('@/views/Home.vue'),
          meta: { title: '项目列表' },
        },
        {
          path: 'create',
          name: 'CreateNovel',
          component: () => import('@/views/CreateNovel.vue'),
          meta: { title: '新建小说' },
        },
        {
          path: 'novel/:id',
          name: 'NovelDetail',
          component: () => import('@/views/NovelDetail.vue'),
          meta: { title: '项目详情' },
        },
        {
          path: 'novel/:id/console',
          name: 'Console',
          component: () => import('@/views/Console.vue'),
          meta: { title: '创作控制台' },
        },
        {
          path: 'novel/:id/chapter/:chapterId',
          name: 'ChapterView',
          component: () => import('@/views/ChapterView.vue'),
          meta: { title: '章节阅读' },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '系统设置' },
        },
        {
          path: 'settings/prompts',
          name: 'PromptSettings',
          component: () => import('@/views/PromptSettings.vue'),
          meta: { title: 'Prompt 管理' },
        },
        {
          path: 'novel/:id/review',
          name: 'OutlineReview',
          component: () => import('@/views/OutlineReview.vue'),
          meta: { title: '大纲审核' },
        },
        {
          path: 'novel/:id/export',
          name: 'Export',
          component: () => import('@/views/Export.vue'),
          meta: { title: '导出与设置' },
        },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
