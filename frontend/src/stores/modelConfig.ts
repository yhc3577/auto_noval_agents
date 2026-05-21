import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'

export interface ModelConfig {
  config_id: string
  name: string
  provider: string
  model: string
  base_url: string
  api_key_masked: string
  is_active: boolean
  max_tokens: number
}

export interface ProviderOption {
  value: string
  label: string
  default_base_url: string
}

export const useModelConfigStore = defineStore('modelConfig', () => {
  const configs = ref<ModelConfig[]>([])
  const activeConfigId = ref<string | null>(null)
  const availableProviders = ref<ProviderOption[]>([])

  async function fetchConfigs() {
    const { data } = await api.get('/model-configs/list')
    configs.value = data.configs
    activeConfigId.value = data.active_config_id
    availableProviders.value = data.available_providers
  }

  async function createConfig(config: {
    name: string
    provider: string
    model: string
    api_key: string
    base_url: string
    max_tokens: number
  }) {
    const { data } = await api.post('/model-configs/create', config)
    return data
  }

  async function updateConfig(configId: string, updates: Record<string, string | number>) {
    const { data } = await api.put('/model-configs/update', { config_id: configId, ...updates })
    return data
  }

  async function deleteConfig(configId: string) {
    const { data } = await api.delete('/model-configs/delete', { data: { config_id: configId } })
    configs.value = configs.value.filter(c => c.config_id !== configId)
    return data
  }

  async function activateConfig(configId: string) {
    const { data } = await api.post('/model-configs/activate', { config_id: configId })
    activeConfigId.value = configId
    return data
  }

  return { configs, activeConfigId, availableProviders, fetchConfigs, createConfig, updateConfig, deleteConfig, activateConfig }
})
