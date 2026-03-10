export const ProvisioningTypeOptions = ['CQRS', 'API', 'GraphQL', 'SharedDB'] as const
export type ProvisioningType = (typeof ProvisioningTypeOptions)[number]

export type FieldInputType = 'text' | 'textarea' | 'select'

export type EditableFieldKey =
  | 'name'
  | 'displayName'
  | 'description'
  | 'template'
  | 'actor'
  | 'category'
  | 'version'
  | 'rootEntity'
  | 'provisioningType'
  | 'isMultipleResult'
  | 'attachedToId'
  | 'attachedToType'
  | 'attachedToName'

export type NodeLabel = 'Command' | 'Event' | 'Policy' | 'Aggregate' | 'ReadModel' | 'UI' | 'BoundedContext'

export type FieldSchema = {
  key: EditableFieldKey
  label: string
  input: FieldInputType
  placeholder?: string
  options?: readonly string[]
  helpText?: string
}

export type NodeEditSchema = {
  label: NodeLabel
  title: string
  fields: FieldSchema[]
}

const CommonFields: FieldSchema[] = [
  { key: 'name', label: '이름', input: 'text', placeholder: 'Name' },
  { key: 'displayName', label: '표시 이름 (UI)', input: 'text', placeholder: 'UI에 표시할 라벨 (한글/영문)' },
  { key: 'description', label: '설명', input: 'textarea', placeholder: 'Description' }
]

export const NodeEditSchemas: Record<NodeLabel, NodeEditSchema> = {
  Command: {
    label: 'Command',
    title: 'Command',
    fields: [
      ...CommonFields,
      {
        key: 'category',
        label: 'Category',
        input: 'select',
        options: ['Create', 'Update', 'Delete', 'Process', 'Business Logic', 'External Integration'],
        helpText: '커맨드의 유형(종류)을 선택합니다.'
      },
      {
        key: 'actor',
        label: 'Actor',
        input: 'text',
        placeholder: '예: Customer / Admin / System',
        helpText: '커맨드를 발생시키는 주체(사람/시스템)를 입력합니다.'
      }
    ]
  },
  Event: {
    label: 'Event',
    title: 'Event',
    fields: [
      ...CommonFields,
      {
        key: 'version',
        label: 'Version',
        input: 'text',
        placeholder: '예: 1',
        helpText: '이벤트 버전(문자열/숫자)을 입력합니다.'
      }
    ]
  },
  Policy: {
    label: 'Policy',
    title: 'Policy',
    fields: [...CommonFields]
  },
  Aggregate: {
    label: 'Aggregate',
    title: 'Aggregate',
    fields: [
      ...CommonFields,
      {
        key: 'rootEntity',
        label: 'Root Entity',
        input: 'text',
        placeholder: '예: Order',
        helpText: 'Aggregate의 루트 엔티티(개념)를 입력합니다.'
      }
    ]
  },
  ReadModel: {
    label: 'ReadModel',
    title: 'ReadModel',
    fields: [
      ...CommonFields,
      {
        key: 'actor',
        label: 'Actor',
        input: 'text',
        placeholder: '예: customer / seller / system',
        helpText: 'ReadModel을 사용하는 주체(사람/시스템)를 입력합니다.'
      },
      {
        key: 'isMultipleResult',
        label: 'Is Multiple Result',
        input: 'select',
        options: ['list', 'collection', 'single result'],
        helpText: 'list: 정렬된 목록, collection: 컬렉션/카탈로그, single result: 단일 항목'
      },
      {
        key: 'provisioningType',
        label: 'Provisioning Type',
        input: 'select',
        options: ProvisioningTypeOptions,
        helpText: 'CQRS/API/GraphQL/SharedDB 중 선택합니다.'
      }
    ]
  },
  UI: {
    label: 'UI',
    title: 'UI',
    fields: [
      ...CommonFields,
      {
        key: 'template',
        label: 'Template (HTML)',
        input: 'textarea',
        placeholder: '<div class="wf-root" data-wf-root="1">...</div>',
        helpText:
          'UI 화면의 body-only HTML 조각을 입력합니다. (서버에서 script/on* 핸들러 제거 등 정규화가 적용될 수 있습니다)'
      },
      {
        key: 'attachedToId',
        label: 'AttachedTo Id',
        input: 'text',
        placeholder: '연결 대상 노드 id',
        helpText: '연결 대상 노드 id를 입력합니다. (존재하지 않으면 저장이 거부됩니다)'
      },
      {
        key: 'attachedToType',
        label: 'AttachedTo Type',
        input: 'text',
        placeholder: '예: Command / ReadModel',
        helpText: '연결 대상 노드 타입(표시용)입니다.'
      },
      {
        key: 'attachedToName',
        label: 'AttachedTo Name',
        input: 'text',
        placeholder: '예: CreateOrder',
        helpText: '연결 대상 노드 이름(표시용)입니다.'
      }
    ]
  },
  BoundedContext: {
    label: 'BoundedContext',
    title: 'Bounded Context',
    fields: [...CommonFields]
  }
}

export function normalizeNodeLabel(raw) {
  const v = String(raw || '').trim()
  if (
    v === 'Command' ||
    v === 'Event' ||
    v === 'Policy' ||
    v === 'Aggregate' ||
    v === 'ReadModel' ||
    v === 'UI' ||
    v === 'BoundedContext'
  ) {
    return v
  }
  // vue-flow node.type is lower-case
  if (v === 'command') return 'Command'
  if (v === 'event') return 'Event'
  if (v === 'policy') return 'Policy'
  if (v === 'aggregate') return 'Aggregate'
  if (v === 'readmodel') return 'ReadModel'
  if (v === 'ui') return 'UI'
  if (v === 'boundedcontext') return 'BoundedContext'
  return 'Policy'
}


