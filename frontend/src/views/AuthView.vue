<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <!-- Logo -->
      <div class="auth-logo">
        <span class="logo-f">F</span>Matrix
      </div>
      <p class="auth-tagline">Financial Intelligence Platform</p>

      <!-- Tab switcher -->
      <div class="auth-tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">Sign In</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">Register</button>
      </div>

      <!-- Error -->
      <Transition name="err">
        <div v-if="auth.error" class="auth-error">{{ auth.error }}</div>
      </Transition>

      <!-- Login Form -->
      <form v-if="mode === 'login'" @submit.prevent="doLogin" class="auth-form">
        <label>
          <span>Email</span>
          <input v-model="loginForm.email" type="email" placeholder="you@company.com" required autocomplete="email" />
        </label>
        <label>
          <span>Password</span>
          <input v-model="loginForm.password" type="password" placeholder="••••••••" required autocomplete="current-password" />
        </label>
        <button type="submit" class="btn-primary" :disabled="auth.loading">
          <span v-if="auth.loading" class="spin" />
          {{ auth.loading ? 'Signing in…' : 'Sign In' }}
        </button>
      </form>

      <!-- Register Form -->
      <form v-else @submit.prevent="doRegister" class="auth-form">
        <div class="form-row">
          <label>
            <span>First Name</span>
            <input v-model="regForm.first_name" type="text" placeholder="John" required />
          </label>
          <label>
            <span>Last Name</span>
            <input v-model="regForm.last_name" type="text" placeholder="Doe" />
          </label>
        </div>
        <label>
          <span>Email</span>
          <input v-model="regForm.email_id" type="email" placeholder="you@company.com" required />
        </label>
        <label>
          <span>Password</span>
          <input v-model="regForm.password" type="password" placeholder="••••••••" required />
        </label>
        <div class="form-row">
          <label>
            <span>Phone (10 digits)</span>
            <input v-model="regForm.phone_no" type="tel" placeholder="9876543210" required maxlength="10" />
          </label>
          <label>
            <span>Organization</span>
            <input v-model="regForm.organization" type="text" placeholder="Acme Corp" required />
          </label>
        </div>
        <button type="submit" class="btn-primary" :disabled="auth.loading">
          <span v-if="auth.loading" class="spin" />
          {{ auth.loading ? 'Creating account…' : 'Create Account' }}
        </button>
      </form>

      <Transition name="err">
        <p v-if="successMsg" class="success-msg">{{ successMsg }}</p>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth   = useAuthStore()
const router = useRouter()
const mode   = ref('login')
const successMsg = ref('')

const loginForm = reactive({ email: '', password: '' })
const regForm   = reactive({
  email_id: '', first_name: '', last_name: '',
  password: '', phone_no: '', organization: ''
})

async function doLogin() {
  auth.error = null
  const ok = await auth.login(loginForm.email, loginForm.password)
  if (ok) router.replace('/')
}

async function doRegister() {
  auth.error = null
  const ok = await auth.register({ ...regForm })
  if (ok) {
    successMsg.value = '✓ Account created! Please sign in.'
    mode.value = 'login'
    setTimeout(() => { successMsg.value = '' }, 4000)
  }
}
</script>

<style scoped>
.auth-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 24px;
}

.auth-card {
  width: 100%; max-width: 480px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 24px; padding: 40px 36px;
  box-shadow: 0 0 80px rgba(124,58,237,.12);
  animation: fadeUp .4s ease both;
}

.auth-logo {
  font-family: var(--font-mono); font-size: 24px; font-weight: 700;
  text-align: center; margin-bottom: 6px;
}
.logo-f { color: var(--purple-light); font-size: 1.4em; }

.auth-tagline {
  text-align: center; color: var(--muted); font-size: 13px; margin-bottom: 28px;
}

.auth-tabs {
  display: flex; background: rgba(255,255,255,.04); border: 1px solid var(--border);
  border-radius: 12px; padding: 4px; gap: 4px; margin-bottom: 24px;
}
.auth-tabs button {
  flex: 1; padding: 9px; border: none; border-radius: 9px; font-size: 14px;
  font-weight: 600; color: var(--muted); background: transparent; transition: all .2s;
}
.auth-tabs button.active {
  background: var(--purple); color: #fff; box-shadow: 0 0 16px var(--purple-glow);
}

.auth-error {
  background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.3);
  color: var(--critical); border-radius: 10px; padding: 10px 14px;
  font-size: 13px; margin-bottom: 16px;
}
.success-msg {
  color: var(--low); font-size: 13px; text-align: center; margin-top: 12px;
}

.auth-form { display: flex; flex-direction: column; gap: 16px; }

.auth-form label {
  display: flex; flex-direction: column; gap: 6px;
}
.auth-form label span {
  font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px;
}
.auth-form input {
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
  border-radius: 10px; padding: 11px 14px; font-size: 14px;
  color: var(--text); outline: none; transition: border-color .2s;
  font-family: var(--font-sans);
}
.auth-form input:focus { border-color: var(--purple); }
.auth-form input::placeholder { color: rgba(148,163,184,.4); }

.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.btn-primary {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  color: #fff; border: none; padding: 13px; border-radius: 12px;
  font-size: 15px; font-weight: 700; cursor: pointer; transition: all .2s;
  box-shadow: 0 0 24px var(--purple-glow); margin-top: 4px;
}
.btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 0 40px var(--purple-glow); }
.btn-primary:disabled { opacity: .55; cursor: not-allowed; }

.spin {
  width: 15px; height: 15px; border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite;
}

.err-enter-active, .err-leave-active { transition: all .25s; }
.err-enter-from, .err-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 480px) {
  .auth-card { padding: 28px 20px; }
  .form-row { grid-template-columns: 1fr; }
}
</style>
