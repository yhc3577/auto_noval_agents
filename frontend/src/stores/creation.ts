import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

interface Progress {
  current_chapter: number
  total_chapters: number
  progress: number
  status: string
  chapter_status: string
  log: string
}

export const useCreationStore = defineStore('creation', () => {
  // 按项目隔离进度状态
  const progressMap = ref<Record<string, Progress>>({})
  const activeProjectId = ref<string>('')
  const isStreaming = ref(false)
  const eventSources = ref<Record<string, EventSource>>({})

  // 流式章节内容
  const streamingContent = ref<Record<string, string>>({})
  const streamingActive = ref<Record<string, boolean>>({})
  const streamEventSources = ref<Record<string, EventSource>>({})

  // 当前活跃项目的进度
  const progress = computed(() => {
    return progressMap.value[activeProjectId.value] || {
      current_chapter: 0,
      total_chapters: 0,
      progress: 0,
      status: 'idle',
      chapter_status: '',
      log: ''
    }
  })

  function setActiveProject(projectId: string) {
    activeProjectId.value = projectId
    // 确保该项目有进度记录
    if (!progressMap.value[projectId]) {
      progressMap.value[projectId] = {
        current_chapter: 0,
        total_chapters: 0,
        progress: 0,
        status: 'idle',
        chapter_status: '',
        log: ''
      }
    }
  }

  async function startCreation(projectId: string) {
    setActiveProject(projectId)
    const { data } = await api.post('/novel/start', { project_id: projectId })
    progressMap.value[projectId] = {
      ...progressMap.value[projectId],
      status: 'writing',
      chapter_status: 'pending',
      log: '创作启动中...',
      // 重置为0，等待 SSE 推送真实值
      current_chapter: 0,
      progress: 0,
    }
    subscribeProgress(projectId)
    return data
  }

  async function pauseCreation(projectId: string) {
    const { data } = await api.post('/novel/pause', { project_id: projectId })
    unsubscribeProgress(projectId)
    progressMap.value[projectId] = {
      ...progressMap.value[projectId],
      status: 'idle',
      chapter_status: '',
      log: '',
    }
    return data
  }

  function subscribeProgress(projectId: string) {
    // 关闭该项目已有的连接
    if (eventSources.value[projectId]) {
      eventSources.value[projectId].close()
    }

    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const token = localStorage.getItem('token') || ''
    const url = `${baseUrl}/novel/progress?project_id=${projectId}&token=${encodeURIComponent(token)}`

    const eventSource = new EventSource(url)
    eventSources.value[projectId] = eventSource
    isStreaming.value = true

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        progressMap.value[projectId] = data

        if (data.status === 'completed' || data.status === 'paused') {
          unsubscribeProgress(projectId)
        }
      } catch (e) {
        console.error('解析进度数据失败:', e)
      }
    }

    eventSource.onerror = () => {
      isStreaming.value = false
      eventSource.close()
      delete eventSources.value[projectId]
      // 连接断开且仍在创作中 → 重置状态
      if (progressMap.value[projectId]?.status === 'writing') {
        progressMap.value[projectId] = {
          ...progressMap.value[projectId],
          status: 'idle',
          chapter_status: '',
          log: ''
        }
      }
    }
  }

  function unsubscribeProgress(projectId?: string) {
    if (projectId) {
      // 关闭指定项目的连接
      if (eventSources.value[projectId]) {
        eventSources.value[projectId].close()
        delete eventSources.value[projectId]
      }
    } else {
      // 关闭所有连接
      Object.keys(eventSources.value).forEach(id => {
        eventSources.value[id].close()
      })
      eventSources.value = {}
    }
    isStreaming.value = Object.keys(eventSources.value).length > 0
  }

  function subscribeStreamContent(projectId: string) {
    if (streamEventSources.value[projectId]) {
      streamEventSources.value[projectId].close()
    }

    streamingContent.value[projectId] = ''
    streamingActive.value[projectId] = true

    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const token = localStorage.getItem('token') || ''
    const url = `${baseUrl}/novel/stream-content?project_id=${projectId}&token=${encodeURIComponent(token)}`

    const eventSource = new EventSource(url)
    streamEventSources.value[projectId] = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'token') {
          streamingContent.value[projectId] = (streamingContent.value[projectId] || '') + data.content
        } else if (data.type === 'done') {
          streamingActive.value[projectId] = false
          eventSource.close()
          delete streamEventSources.value[projectId]
        }
      } catch (e) {
        console.error('解析流式内容失败:', e)
      }
    }

    eventSource.onerror = () => {
      streamingActive.value[projectId] = false
      eventSource.close()
      delete streamEventSources.value[projectId]
    }
  }

  function unsubscribeStreamContent(projectId?: string) {
    if (projectId) {
      if (streamEventSources.value[projectId]) {
        streamEventSources.value[projectId].close()
        delete streamEventSources.value[projectId]
      }
      streamingActive.value[projectId] = false
    } else {
      Object.keys(streamEventSources.value).forEach(id => {
        streamEventSources.value[id].close()
      })
      streamEventSources.value = {}
      streamingActive.value = {}
    }
  }

  return {
    progress,
    progressMap,
    isStreaming,
    streamingContent,
    streamingActive,
    activeProjectId,
    setActiveProject,
    startCreation,
    pauseCreation,
    subscribeProgress,
    unsubscribeProgress,
    subscribeStreamContent,
    unsubscribeStreamContent
  }
})
