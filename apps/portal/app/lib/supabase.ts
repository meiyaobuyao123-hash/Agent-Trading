import { createClient as createSupabaseClient } from '@supabase/supabase-js'

export function createClient() {
  // 数据库已迁移到云端服务器本地 PostgreSQL + PostgREST
  // NEXT_PUBLIC_SUPABASE_URL 现在指向 http://localhost:3001（PostgREST）
  // NEXT_PUBLIC_SUPABASE_ANON_KEY 现在是 PostgREST JWT
  return createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
