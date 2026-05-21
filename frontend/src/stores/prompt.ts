import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'

export interface PromptTemplate {
  prompt_key: string
  name: string
  description: string
  agent_type: string
  agent_label: string
  prompt_type: string
  variables: string[]
  default_content: string
  current_content: string
  is_customized: boolean
  version: number
  updated_at: string | null
}

export interface AgentGroup {
  agent_type: string
  agent_label: string
  prompts: {
    prompt_key: string
    name: string
    description: string
    prompt_type: string
    variables: string[]
  }[]
}

export const usePromptStore = defineStore('prompt', () => {
  const items = ref<PromptTemplate[]>([])
  const loading = ref(false)
  const selectedAgent = ref<string>('')

  async function fetchList(agentType?: string) {
    loading.value = true
    try {
      const params = agentType ? { agent_type: agentType } : {}
      const { data } = await api.get('/prompts/list', { params })
      items.value = data.items
    } finally {
      loading.value = false
    }
  }

  async function updatePrompt(promptKey: string, templateContent: string) {
    const { data } = await api.put('/prompts/update', {
      prompt_key: promptKey,
      template_content: templateContent,
    })
    // 更新本地列表
    const item = items.value.find(i => i.prompt_key === promptKey)
    if (item) {
      item.current_content = templateContent
      item.is_customized = true
    }
    return data
  }

  async function resetPrompt(promptKey: string) {
    const { data } = await api.post('/prompts/reset', { prompt_key: promptKey })
    // 更新本地列表
    const item = items.value.find(i => i.prompt_key === promptKey)
    if (item) {
      item.current_content = item.default_content
      item.is_customized = false
      item.version = 0
    }
    return data
  }

  async function resetAll() {
    const { data } = await api.post('/prompts/reset-all')
    // 全部重置
    items.value.forEach(item => {
      item.current_content = item.default_content
      item.is_customized = false
      item.version = 0
    })
    return data
  }

  return { items, loading, selectedAgent, fetchList, updatePrompt, resetPrompt, resetAll }
})
