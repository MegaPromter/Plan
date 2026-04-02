<template>
  <tr>
    <td style="color:var(--muted);font-size:12px;text-align:center">{{ index + 1 }}</td>
    <td :title="notice.ii_pi">
      {{ notice.ii_pi || '\u2014' }}
      <span :class="notice.is_auto ? 'badge-sm tt-auto' : 'badge-sm tt-manual'"
            :title="notice.is_auto ? 'Запись создана на основании отчёта' : 'Запись создана вручную'">
        {{ notice.is_auto ? 'Авто' : 'Ручное' }}
      </span>
    </td>
    <td :title="notice.notice_number">{{ notice.notice_number || '\u2014' }}</td>
    <td :title="notice.subject">{{ notice.subject || '\u2014' }}</td>
    <td :title="notice.doc_designation">{{ notice.doc_designation || '\u2014' }}</td>
    <td>{{ notice.date_issued || '\u2014' }}</td>
    <td>{{ notice.date_expires || '\u2014' }}</td>
    <td :title="notice.dept_name">{{ notice.dept || '\u2014' }}</td>
    <td :title="notice.sector">{{ notice.sector || '\u2014' }}</td>
    <td :title="notice.executor">{{ notice.executor || '\u2014' }}</td>
    <td :title="notice.description">{{ notice.description || '\u2014' }}</td>
    <td><span :class="'badge-sm ' + badgeClass">{{ badgeText }}</span></td>
    <td class="col-actions" style="text-align:center;white-space:nowrap">
      <button v-if="canEdit" class="ji-btn" @click="$emit('edit', notice.id)" title="Редактировать">&#9998;</button>
      <button class="ji-btn" @click="$emit('desc', notice.id)" title="Описание">&#128221;</button>
      <button v-if="canClose" class="ji-btn ji-btn-close" @click="$emit('close', notice.id)" title="Погасить">&#9745;</button>
      <button v-if="canDelete" class="ji-btn ji-btn-del" @click="$emit('delete', notice.id)" title="Удалить">&#10005;</button>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  notice: { type: Object, required: true },
  index: { type: Number, required: true },
  canModify: { type: Boolean, default: false },
  canClose: { type: Boolean, default: false },
  canEdit: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
})

defineEmits(['edit', 'desc', 'close', 'delete'])

const STATUS_MAP = {
  active:     ['badge-active',    'Действует'],
  expired:    ['badge-expired',   'Просрочено'],
  closed_no:  ['badge-closed-no', 'Погашено без внесения'],
  closed_yes: ['badge-closed-yes','Погашено с внесением'],
}

const badgeClass = computed(() => (STATUS_MAP[props.notice.status] || ['badge-closed-yes'])[0])
const badgeText = computed(() => (STATUS_MAP[props.notice.status] || [, props.notice.status || '\u2014'])[1])
</script>
