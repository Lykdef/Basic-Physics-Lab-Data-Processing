<script setup lang="ts">
import { ref, watch } from 'vue';
const props=defineProps<{modelValue:number;nonnegative?:boolean}>();
const emit=defineEmits<{'update:modelValue':[number];invalid:[boolean]}>();
const draft=ref(String(props.modelValue)),focused=ref(false);
watch(()=>props.modelValue,value=>{if(!focused.value){draft.value=String(value);emit('invalid',false);}});
function input(event:Event){
  draft.value=(event.target as HTMLInputElement).value;
  const raw=draft.value.trim(),value=Number(raw);
  const valid=/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(raw) && Number.isFinite(value) && (!props.nonnegative || value>=0);
  emit('invalid',!valid);if(valid)emit('update:modelValue',value);
}
</script>
<template><input type="text" inputmode="decimal" :value="draft" @focus="focused=true" @blur="focused=false" @input="input"/></template>
