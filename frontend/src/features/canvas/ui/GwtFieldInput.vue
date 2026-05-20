<script setup>
import { computed } from 'vue'

/**
 * Single GWT field value editor. Renders the correct control (select / checkbox /
 * ValueObject / typed input) based on the property metadata. Used by the card
 * layout of the Given/When/Then modal.
 */
const props = defineProps({
  modelValue: { default: '' },
  prop: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'edit-vo'])

function lc(v) {
  return v ? String(v).toLowerCase() : ''
}

const isEnum = computed(() => props.prop?.fieldType === 'enum' || lc(props.prop?.type) === 'enum')
const isVo = computed(
  () => props.prop?.fieldType === 'valueObject' || lc(props.prop?.type) === 'valueobject',
)

const inputType = computed(() => {
  const type = lc(props.prop?.type)
  if (type.includes('int') || type.includes('long') || type === 'integer') return 'number'
  if (
    type.includes('decimal') ||
    type.includes('bigdecimal') ||
    type.includes('double') ||
    type.includes('float')
  )
    return 'number'
  if (type.includes('boolean') || type === 'bool') return 'checkbox'
  if (type.includes('datetime') || type.includes('timestamp')) return 'datetime-local'
  if (type.includes('date')) return 'date'
  if (type.includes('time')) return 'time'
  return 'text'
})

const isNumberType = computed(() => {
  const type = lc(props.prop?.type)
  return (
    type.includes('int') ||
    type.includes('long') ||
    type === 'integer' ||
    type.includes('decimal') ||
    type.includes('bigdecimal') ||
    type.includes('double') ||
    type.includes('float')
  )
})

const step = computed(() => {
  const type = lc(props.prop?.type)
  if (
    type.includes('decimal') ||
    type.includes('bigdecimal') ||
    type.includes('double') ||
    type.includes('float')
  )
    return '0.01'
  return undefined
})

function parseBoolean(value) {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const lower = value.toLowerCase().replace(/^["']|["']$/g, '')
    return lower === 'true' || lower === '1'
  }
  if (typeof value === 'number') return value !== 0
  return Boolean(value)
}

const displayValue = computed(() => {
  const value = props.modelValue
  if (value === null || value === undefined) return ''
  if (isVo.value) {
    if (typeof value === 'object') return JSON.stringify(value, null, 2)
    if (typeof value === 'string') {
      try {
        return JSON.stringify(JSON.parse(value), null, 2)
      } catch {
        return value
      }
    }
    return String(value)
  }
  if (isNumberType.value) {
    if (typeof value === 'number') return String(value)
    if (typeof value === 'string') {
      const unquoted = value.replace(/^["']|["']$/g, '')
      const num = parseFloat(unquoted)
      return isNaN(num) ? unquoted : String(num)
    }
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
})

const placeholder = computed(() => {
  const type = lc(props.prop?.type)
  if (isEnum.value) return '-- 선택 --'
  if (type.includes('int') || type.includes('long') || type === 'integer') return '123'
  if (
    type.includes('decimal') ||
    type.includes('bigdecimal') ||
    type.includes('double') ||
    type.includes('float')
  )
    return '100.50'
  if (type.includes('datetime') || type.includes('timestamp')) return '2024-01-15T10:30:00'
  if (type.includes('date')) return '2024-01-15'
  if (type.includes('uuid')) return '550e8400-e29b-41d4-...'
  return '값 입력'
})
</script>

<template>
  <!-- Enum -->
  <select
    v-if="isEnum"
    class="gwt-field-input"
    :value="displayValue"
    :disabled="disabled"
    @change="emit('update:modelValue', $event.target.value)"
  >
    <option value="">-- 선택 --</option>
    <option v-for="item in prop.enumItems || []" :key="item" :value="item">{{ item }}</option>
  </select>

  <!-- Boolean -->
  <label v-else-if="inputType === 'checkbox'" class="gwt-field-checkbox">
    <input
      type="checkbox"
      :checked="parseBoolean(modelValue)"
      :disabled="disabled"
      @change="emit('update:modelValue', $event.target.checked)"
    />
  </label>

  <!-- ValueObject -->
  <div v-else-if="isVo" class="gwt-field-vo">
    <textarea
      class="gwt-field-input gwt-field-textarea"
      :value="displayValue"
      rows="2"
      readonly
      :disabled="disabled"
    />
    <button
      type="button"
      class="gwt-field-vo-btn"
      :disabled="disabled"
      title="ValueObject 구조 편집"
      @click="emit('edit-vo')"
    >
      ✏️
    </button>
  </div>

  <!-- Typed input -->
  <input
    v-else
    class="gwt-field-input"
    :type="inputType"
    :value="displayValue"
    :placeholder="placeholder"
    :step="step"
    :disabled="disabled"
    @input="emit('update:modelValue', $event.target.value)"
  />
</template>

<style scoped>
.gwt-field-input {
  width: 100%;
  padding: 5px 8px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-bright);
  font-size: 0.78rem;
  box-sizing: border-box;
}

.gwt-field-input:focus {
  outline: none;
  border-color: var(--color-accent, #5b8cff);
}

.gwt-field-textarea {
  resize: vertical;
  font-family: var(--font-mono, monospace);
}

.gwt-field-checkbox {
  display: flex;
  align-items: center;
  height: 100%;
}

.gwt-field-checkbox input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.gwt-field-vo {
  display: flex;
  gap: 4px;
  align-items: flex-start;
}

.gwt-field-vo-btn {
  flex-shrink: 0;
  padding: 4px 6px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.75rem;
}

.gwt-field-vo-btn:hover:not(:disabled) {
  background: var(--color-bg);
}
</style>
