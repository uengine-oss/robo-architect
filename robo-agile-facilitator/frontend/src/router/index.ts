import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue')
    },
    {
      path: '/session/:id',
      name: 'session',
      component: () => import('../views/SessionView.vue'),
      props: true
    }
  ]
})

export default router


