export type WireframeElementType = 'frame' | 'rectangle' | 'text' | 'ellipse' | 'button' | 'input' | 'navbar' | 'card' | 'sidebar'

export interface WireframeElement {
  id: string
  type: WireframeElementType
  x: number
  y: number
  width: number
  height: number
  label?: string
  children?: WireframeElement[]
  fillColor?: string
  strokeColor?: string
  strokeWidth?: number
  cornerRadius?: number
  fontSize?: number
  textAlign?: 'LEFT' | 'CENTER' | 'RIGHT'
  opacity?: number
}
