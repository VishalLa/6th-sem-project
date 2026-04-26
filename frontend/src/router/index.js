import { createRouter, createWebHashHistory } from 'vue-router'
import HomeView         from '@/views/HomeView.vue'
import SummaryView      from '@/views/SummaryView.vue'
import GraphView        from '@/views/GraphView.vue'
import MetricsView      from '@/views/MetricsView.vue'
import TransactionsView from '@/views/TransactionsView.vue'
import AuthView         from '@/views/AuthView.vue'
import ChatView         from '@/views/ChatView.vue'
import BatchesView      from '@/views/BatchesView.vue'

const routes = [
  { path: '/auth',         name: 'auth',         component: AuthView,         meta: { public: true } },
  { path: '/',             name: 'home',         component: HomeView          },
  { path: '/summary',      name: 'summary',      component: SummaryView       },
  { path: '/graph',        name: 'graph',        component: GraphView         },
  { path: '/metrics',      name: 'metrics',      component: MetricsView       },
  { path: '/transactions', name: 'transactions', component: TransactionsView  },
  { path: '/chat',         name: 'chat',         component: ChatView          },
  { path: '/batches',      name: 'batches',      component: BatchesView       },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach(async (to) => {
  // Lazy-import to avoid circular dependency (store uses router indirectly)
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()

  // Wait for the initial token validation to finish before deciding.
  // This prevents the flicker where a user with an expired token briefly
  // sees the home page before being redirected to /auth.
  if (auth.validating) {
    await new Promise(resolve => {
      const stop = auth.$watch
        ? null  // pinia doesn't expose $watch directly, use interval
        : null
      const interval = setInterval(() => {
        if (!auth.validating) { clearInterval(interval); resolve() }
      }, 20)
    })
  }

  const loggedIn = auth.isLoggedIn

  if (!to.meta.public && !loggedIn) return { name: 'auth' }
  if (to.name === 'auth' && loggedIn) return { name: 'home' }
})

export default router
