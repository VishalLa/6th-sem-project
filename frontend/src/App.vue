<template>
  <div class="app">
    <div class="bg-grid" />
    <div class="bg-orb orb1" />
    <div class="bg-orb orb2" />
    <div class="bg-orb orb3" />

    <AppNavbar />

    <main>
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup>
import AppNavbar from '@/components/AppNavbar.vue'
</script>

<style scoped>
.app { min-height:100vh; position:relative; }

.bg-grid {
  position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image:
    linear-gradient(rgba(124,58,237,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124,58,237,.05) 1px, transparent 1px);
  background-size: 40px 40px;
}

.bg-orb { position:fixed; border-radius:50%; filter:blur(80px); pointer-events:none; z-index:0; }
.orb1 { width:500px; height:500px; background:rgba(124,58,237,.15); top:-100px;  left:-100px; }
.orb2 { width:400px; height:400px; background:rgba(168,85,247,.10); bottom:-50px; right:-50px; }
.orb3 { width:300px; height:300px; background:rgba(192,132,252,.08); top:40%; left:50%; transform:translateX(-50%); }

main { position:relative; z-index:1; }
</style>
