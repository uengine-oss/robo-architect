<script setup>
import ReadModelCQRSEditor from './ReadModelCQRSEditor.vue'

const props = defineProps({
  visible: Boolean,
  readModelId: String,
  readModelData: Object
})

const emit = defineEmits(['close', 'save', 'updated'])

// Close modal
function close() {
  emit('close')
}
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="close">
    <div class="modal-container">
      <div class="modal-header">
        <h3>ReadModel CQRS 설정</h3>
        <span class="modal-subtitle">{{ readModelData?.name }}</span>
        <button class="close-btn" @click="close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <ReadModelCQRSEditor
          :enabled="visible"
          :read-model-id="readModelId"
          :read-model-data="readModelData"
          @updated="$emit('updated')"
        />
      </div>

      <div class="modal-footer">
        <button class="btn-close" @click="close">닫기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: #1a1a2e;
  border-radius: 12px;
  width: 800px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  border: 1px solid #2d2d4d;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #2d2d4d;
  background: linear-gradient(135deg, #40c057 0%, #2f9e44 100%);
  border-radius: 12px 12px 0 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #fff;
}

.modal-subtitle {
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
}

.close-btn {
  margin-left: auto;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 12px;
  color: #808080;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #2d2d4d;
  border-top-color: #40c057;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.section {
  margin-bottom: 24px;
}

.section h4 {
  margin: 0 0 12px 0;
  font-size: 0.9rem;
  color: #c0c0c0;
}

.provisioning-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.provisioning-option {
  flex: 1;
  min-width: 140px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #252540;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.provisioning-option:hover {
  background: #2d2d50;
}

.provisioning-option.selected {
  border-color: #40c057;
  background: rgba(64, 192, 87, 0.1);
}

.provisioning-option input {
  margin-top: 2px;
  accent-color: #40c057;
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-label {
  font-weight: 600;
  color: #e0e0e0;
  font-size: 0.85rem;
}

.option-desc {
  font-size: 0.7rem;
  color: #707090;
}

.cqrs-section {
  background: #1e1e35;
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
}

.btn-add {
  background: linear-gradient(135deg, #40c057 0%, #2f9e44 100%);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn-add:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 192, 87, 0.3);
}

.btn-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.add-operation-form {
  background: #252540;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.type-select {
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #e0e0e0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
}

.when-label {
  color: #707090;
  font-size: 0.8rem;
}

.event-select {
  flex: 1;
  min-width: 200px;
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #e0e0e0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
}

.btn-confirm {
  background: #40c057;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
}

.btn-confirm:disabled {
  opacity: 0.5;
}

.btn-cancel-form {
  background: #3d3d6d;
  color: #a0a0a0;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
}

.empty-rules {
  text-align: center;
  color: #505070;
  padding: 32px;
  font-size: 0.85rem;
  background: #252540;
  border-radius: 8px;
}

.cqrs-operation {
  background: #252540;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
  border-left: 4px solid #40c057;
}

.cqrs-operation.update {
  border-left-color: #5c7cfa;
}

.cqrs-operation.delete {
  border-left-color: #ff6b6b;
}

.operation-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #3d3d6d;
}

.operation-type {
  background: #40c057;
  color: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
}

.cqrs-operation.update .operation-type {
  background: #5c7cfa;
}

.cqrs-operation.delete .operation-type {
  background: #ff6b6b;
}

.when-text {
  color: #707090;
  font-size: 0.8rem;
}

.event-name {
  color: #fd7e14;
  font-weight: 600;
  font-size: 0.9rem;
}

.btn-delete-op {
  margin-left: auto;
  background: none;
  border: none;
  color: #ff6b6b;
  cursor: pointer;
  padding: 4px;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.btn-delete-op:hover {
  opacity: 1;
}

.mapping-section,
.where-section {
  margin-top: 12px;
}

.section-label {
  font-size: 0.75rem;
  color: #707090;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mapping-row,
.where-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #1a1a2e;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 0.85rem;
}

.target-field {
  color: #40c057;
  font-weight: 500;
}

.equals,
.operator {
  color: #707090;
}

.source-field {
  color: #fd7e14;
}

.source-field.static {
  color: #fcc419;
}

.btn-remove-mapping {
  margin-left: auto;
  background: none;
  border: none;
  color: #505070;
  cursor: pointer;
  padding: 2px;
}

.btn-remove-mapping:hover {
  color: #ff6b6b;
}

.add-mapping-form,
.add-where-form {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: rgba(64, 192, 87, 0.05);
  border: 1px dashed #3d3d6d;
  border-radius: 6px;
  margin-top: 8px;
}

.field-select,
.source-type-select,
.operator-select {
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #c0c0c0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.field-select {
  flex: 1;
  min-width: 120px;
}

.source-type-select {
  width: 80px;
}

.operator-select {
  width: 50px;
}

.value-input {
  flex: 1;
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #c0c0c0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.btn-add-small {
  background: #40c057;
  color: #fff;
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-add-small:disabled {
  opacity: 0.5;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #2d2d4d;
}

.saving-indicator {
  color: #40c057;
  font-size: 0.85rem;
  margin-right: auto;
}

.btn-close {
  background: linear-gradient(135deg, #3d3d6d 0%, #2d2d4d 100%);
  color: #e0e0e0;
  border: none;
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.btn-close:hover {
  transform: translateY(-1px);
}
</style>


