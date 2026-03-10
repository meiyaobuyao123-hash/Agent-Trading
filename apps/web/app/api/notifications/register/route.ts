/**
 * POST /api/notifications/register
 * 注册设备推送令牌（FCM Token / APNs Token）
 *
 * 当前阶段：将 token 存入 Supabase device_tokens 表，
 * 供后续 Phase 3 的真实 FCM 推送使用。
 *
 * Body: {
 *   token: string        // FCM device token
 *   platform: 'ios' | 'android'
 *   userId?: string      // Supabase auth user ID（可选，未登录时匿名）
 *   appVersion?: string  // App 版本号
 * }
 *
 * POST /api/notifications/send
 * 向所有已注册设备发送推送（Admin 专用，需 CRON_SECRET 验证）
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  return createClient(url, key)
}

// ── 注册设备 token ──────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { token, platform, userId, appVersion } = body as {
    token?: string
    platform?: string
    userId?: string
    appVersion?: string
  }

  if (!token || !platform) {
    return NextResponse.json(
      { error: 'token and platform are required' },
      { status: 400 }
    )
  }

  if (!['ios', 'android'].includes(platform)) {
    return NextResponse.json(
      { error: 'platform must be ios or android' },
      { status: 400 }
    )
  }

  const supabase = getSupabase()

  if (!supabase) {
    // Supabase 未配置 → 仍返回 200（token 注册为 no-op）
    return NextResponse.json({
      ok: true,
      message: 'Supabase not configured — token not persisted (dev mode)',
      token: token.slice(0, 8) + '...',
    })
  }

  // Upsert: 同一 token 更新 updated_at 即可
  const { error } = await supabase.from('device_tokens').upsert(
    {
      token,
      platform,
      user_id: userId ?? null,
      app_version: appVersion ?? null,
      updated_at: new Date().toISOString(),
    },
    { onConflict: 'token' }
  )

  if (error) {
    // 表可能不存在（migration 未执行） → 返回 200 降级
    console.warn('[notifications/register]', error.message)
    return NextResponse.json({
      ok: true,
      message: `Token received but not stored: ${error.message}`,
    })
  }

  return NextResponse.json({
    ok: true,
    message: 'Device token registered successfully',
    platform,
  })
}

// ── 查询已注册设备数量（GET） ──────────────────────────────────────────────

export async function GET() {
  const supabase = getSupabase()
  if (!supabase) {
    return NextResponse.json({ count: 0, message: 'Supabase not configured' })
  }

  const { count, error } = await supabase
    .from('device_tokens')
    .select('*', { count: 'exact', head: true })

  if (error) {
    return NextResponse.json({ count: 0, error: error.message })
  }

  return NextResponse.json({ count: count ?? 0 })
}
