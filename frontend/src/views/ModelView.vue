<script setup lang="ts">
import { Button, InputNumber, Textarea, ToggleSwitch } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { ref } from 'vue'
import BoxContainer from '@/components/BoxContainer.vue'
import ConfigItem from '@/components/ConfigItem.vue'

const toast = useToast()

const timeLimit = ref(300)
const creditLimit = ref(1000)
const wantFriends = ref(true)
const friendDescription = ref('')

function startTravel() {
  toast.add({ severity: 'info', summary: '提示', detail: '功能即将上线，敬请期待', life: 3000 })
}
</script>

<template>
  <BoxContainer class="text-sm">
    <div class="flex flex-col gap-5 p-2 pb-8">
      <!-- 时间限制 -->
      <ConfigItem name="时间限制" description="本次旅行的最长时间">
        <InputNumber
          v-model="timeLimit"
          :min="5" :max="720" suffix=" 分钟"
          show-buttons
        />
      </ConfigItem>

      <!-- 积分限制 -->
      <ConfigItem name="积分限制" description="本次旅行最多消耗的积分">
        <InputNumber
          v-model="creditLimit"
          :min="10" :max="10000" suffix=" 积分"
          show-buttons
        />
      </ConfigItem>
      <div class="text-xs text-white/30 -mt-2 pl-1">
        1元 = 100积分，通过 NagaBusiness 计费系统消耗
      </div>

      <div class="border-t border-white/8 my-1" />

      <!-- 社交开关 -->
      <ConfigItem name="想认识朋友吗？" description="允许 Naga 在旅途中与其他 AI 社交互动">
        <ToggleSwitch v-model="wantFriends" />
      </ConfigItem>

      <!-- 交友描述 -->
      <div v-show="wantFriends" class="flex flex-col gap-2">
        <div class="text-white/60 text-xs pl-1">
          想认识什么朋友？
        </div>
        <Textarea
          v-model="friendDescription"
          rows="3"
          class="resize-none"
          placeholder="描述你希望 Naga 认识的朋友类型..."
        />
      </div>

      <!-- 出发按钮 -->
      <div class="flex justify-center mt-2">
        <Button
          label="出发！"
          class="px-8!"
          @click="startTravel"
        />
      </div>

      <div class="border-t border-white/8 my-1" />

      <!-- 上次旅行 -->
      <div class="flex flex-col gap-2">
        <div class="text-white/40 text-xs">
          上次旅行
        </div>
        <div class="flex items-center justify-center min-h-20 rounded-lg border border-white/6 bg-white/2 text-white/25 text-sm">
          暂无旅行记录
        </div>
      </div>
    </div>
  </BoxContainer>
</template>
