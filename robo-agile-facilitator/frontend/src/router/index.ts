import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../features/eventStorming/pages/HomePage.vue')
    },
    {
      path: '/session/:id',
      name: 'session',
      component: () => import('../features/eventStorming/pages/SessionPage.vue'),
      props: true
    }
  ]
})

export default router


