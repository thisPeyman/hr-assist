import type { PipelineOwner } from "@/lib/api"

export const roleStatusLabels = { draft: "پیش‌نویس", open: "باز", paused: "متوقف", closed: "بسته" }

export function ownerLabel(owners: PipelineOwner[], id: string | null) {
  if (!id) return "بدون مسئول"
  const owner = owners.find(item => item.id === id)
  return owner ? `${owner.email}${owner.active ? "" : " (غیرفعال)"}` : "مسئول پیشین"
}
