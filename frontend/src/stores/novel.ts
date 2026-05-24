import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'

interface NovelProject {
  project_id: string
  title: string
  genre: string
  status: string
  current_chapter: number
  chapter_count: number
  created_at: string
}

export const useNovelStore = defineStore('novel', () => {
  const novels = ref<NovelProject[]>([])
  const total = ref(0)
  const currentNovel = ref<any>(null)

  async function fetchNovels(page = 1, pageSize = 20) {
    const { data } = await api.get('/novel/list', {
      params: { page, page_size: pageSize }
    })
    novels.value = data.items
    total.value = data.total
  }

  async function fetchNovelDetail(projectId: string) {
    const { data } = await api.get('/novel/detail', {
      params: { project_id: projectId }
    })
    currentNovel.value = data
    return data
  }

  async function createNovel(config: any) {
    const { data } = await api.post('/novel/create', config)
    return data
  }

  async function regenerateOutline(projectId: string) {
    const { data } = await api.post('/novel/regenerate-outline', {
      project_id: projectId
    })
    return data
  }

  async function updateNovel(projectId: string, updates: any) {
    const { data } = await api.put('/novel/update', {
      project_id: projectId,
      ...updates
    })
    return data
  }

  async function deleteNovel(projectId: string) {
    const { data } = await api.delete('/novel/delete', {
      data: { project_id: projectId }
    })
    novels.value = novels.value.filter(n => n.project_id !== projectId)
    return data
  }

  async function reviewOutline(projectId: string, approved: boolean, feedback = '') {
    const { data } = await api.post('/novel/outline/review', {
      project_id: projectId,
      approved,
      feedback,
    })
    return data
  }

  async function updateOutline(payload: any) {
    const { data } = await api.put('/novel/outline/update', payload)
    return data
  }

  return { novels, total, currentNovel, fetchNovels, fetchNovelDetail, createNovel, regenerateOutline, updateNovel, deleteNovel, reviewOutline, updateOutline }
})
