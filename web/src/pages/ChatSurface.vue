<template>
  <UserChat v-if="userToken" />
  <Dashboard v-else />
</template>
<script setup>
import Dashboard from './Dashboard.vue'
import UserChat from './UserChat.vue'
import { getToken } from '../userApi'

const userToken = getToken()
</script>
