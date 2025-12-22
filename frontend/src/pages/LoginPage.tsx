import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Card } from '../components/ui/card'

const schema = z.object({
  tenant_id: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(1),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const [loginError, setLoginError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { tenant_id: 'demo', email: 'admin@demo.com' } })

  useEffect(() => {
    if (token) navigate('/')
  }, [token])

  const onSubmit = async (values: FormValues) => {
    setLoginError(null)
    try {
      await login(values)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setLoginError(message)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-md space-y-4">
        <div>
          <h1 className="text-2xl font-semibold">Sign in</h1>
          <p className="text-sm text-slate-600">Use your tenant credentials.</p>
        </div>
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
          {loginError ? <p className="text-sm text-red-600">{loginError}</p> : null}
          <div>
            <label className="text-sm font-medium text-slate-700">Tenant</label>
            <Input {...register('tenant_id')} placeholder="demo" />
            {errors.tenant_id && <p className="text-xs text-red-600">{errors.tenant_id.message}</p>}
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Email</label>
            <Input type="email" {...register('email')} placeholder="admin@demo.com" />
            {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Password</label>
            <Input type="password" {...register('password')} />
            {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Login'}
          </Button>
          <p className="text-xs text-slate-500">Default: tenant demo / admin@demo.com / password</p>
        </form>
      </Card>
    </div>
  )
}
