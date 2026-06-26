// 온라인 쇼핑몰 백엔드 REST API 클라이언트.
// 단일 배포 단위(MONOLITH)이므로 게이트웨이 없이 백엔드에 직접 호출한다.
const BASE = import.meta.env.VITE_SHOP_API_BASE ?? '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${options.method ?? 'GET'} ${path} 실패: ${res.status}`)
  }
  return res.status === 204 ? null : res.json()
}

export const cartApi = {
  addItem: (customerId, productId, quantity) =>
    request('/carts/items', {
      method: 'POST',
      body: JSON.stringify({ customerId, productId, quantity }),
    }),
  removeItem: (cartId, productId) =>
    request(`/carts/${cartId}/items/${productId}`, { method: 'DELETE' }),
  checkout: (cartId) =>
    request(`/carts/${cartId}/checkout`, { method: 'POST' }),
}

export const orderApi = {
  getStatus: (orderId) => request(`/orders/${orderId}`),
  cancel: (orderId, reason) =>
    request(`/orders/${orderId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
}
