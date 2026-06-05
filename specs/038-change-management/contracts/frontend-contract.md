# Frontend Contract: Requirement Change Management (038)

## 컴포넌트 구조

```text
frontend/src/features/requirements/ui/
├── ChangesPanel.vue        # Changes 탭 메인 패널 (목록 + 필터)
├── ChangeDetail.vue        # Change 상세 (EFFECT, 이력, 승인 버튼)
├── ChangeImpactView.vue    # EFFECT 관계 시각화 (영향받는 노드 목록)
├── ChangeUSProposals.vue   # DIRECT_EDIT 진입: 수정된 US/Feature 확인
├── ChangeDesignPlan.vue    # 설계 변경 계획 표시 (robo-change-plan 결과)
└── ChangeTasksView.vue     # 구현 태스크 진행 상황 (SSE 연결)
```

## RequirementsPanel.vue 탭 추가

기존 탭 목록에 **Changes** 탭 추가:
```vue
<!-- RequirementsPanel.vue -->
<v-tab value="changes">Changes</v-tab>
...
<v-window-item value="changes">
  <ChangesPanel />
</v-window-item>
```

## requirements.store.js 신규 액션

```javascript
// requirements.store.js에 추가할 액션들

// Change 목록 조회
async fetchChanges(filters = {}) { ... }

// Change 생성
async createChange(payload) {
  // POST /api/requirement-changes/
  // sourceType: MANUAL | PROMPT | DIRECT_EDIT
}

// 상태 전이
async submitChange(id) { ... }
async approveChange(id, comment) { ... }
async rejectChange(id, comment) { ... }

// 구현 시작 (SSE)
async implementChange(id, includePriorChangeIds = []) {
  // EventSource('/api/requirement-changes/{id}/implement')
  // 태스크 진행 상황 스토어에 반영
}

// 영향도 & 회귀
async fetchImpact(id) { ... }
async fetchRegression(id) { ... }
```

## UserStoryDetail.vue / EpicDetail.vue 수정 범위

직접 수정(DIRECT_EDIT) Change 자동 생성:
```javascript
// 저장 버튼 핸들러에 추가
async onSave() {
  await updateUserStory(this.story);
  // 수정된 노드를 DIRECT_EDIT Change로 등록
  await this.requirementsStore.createChange({
    title: `${this.story.title} 직접 수정`,
    originalPrompt: `사용자가 ${this.story.title}을 직접 수정함`,
    sourceType: 'DIRECT_EDIT',
    directAffectedNodeIds: [this.story.id]
  });
}
```

## SSE 연결 패턴 (ChangeTasksView.vue)

```javascript
// Constitution III: EventSource 사용
const source = new EventSource(`/api/requirement-changes/${changeId}/implement`, {
  method: 'POST',
  body: JSON.stringify({ includePriorChangeIds })
});

source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  this.progress = data;  // ImplementationProgress
  if (data.phase === 'done') source.close();
};
```

## 상태 배지 색상 규칙

| Status | 색상 |
|--------|------|
| DRAFT | grey |
| SUBMITTED | blue |
| APPROVED | green |
| REJECTED | red |
| IMPLEMENTED | purple |

## 자기 승인 방지 UI

승인 버튼은 `change.author !== currentUser.id`인 경우에만 활성화:
```vue
<v-btn :disabled="change.author === currentUser" @click="approve">승인</v-btn>
```
