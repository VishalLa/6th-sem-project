import { createRouter, createWebHashHistory } from 'vue-router'
import HomeView    from '@/views/HomeView.vue'
import SummaryView from '@/views/SummaryView.vue'
import GraphView   from '@/views/GraphView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/',        name: 'home',    component: HomeView    },
    { path: '/summary', name: 'summary', component: SummaryView },
    { path: '/graph',   name: 'graph',   component: GraphView   },
  ]
})