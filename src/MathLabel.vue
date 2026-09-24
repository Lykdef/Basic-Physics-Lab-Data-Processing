<script setup lang="ts">
import {mathParts} from './math-label';
defineProps<{text:string}>();
</script>
<template><span class="math-label"><template v-for="(part,i) in mathParts(text)" :key="i"><sub v-if="part.kind==='sub'">{{part.text}}</sub><sup v-else-if="part.kind==='sup'">{{part.text}}</sup><template v-else>{{part.text}}</template></template></span></template>
