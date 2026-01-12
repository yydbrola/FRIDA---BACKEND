-- ============================================================
-- FRIDA: Tabela users
-- Executar 1x apenas no Supabase Dashboard → SQL Editor
-- ============================================================

-- Criar tabela
CREATE TABLE public.users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT CHECK (role IN ('admin', 'user')) DEFAULT 'user' NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes para queries rápidas
CREATE INDEX idx_users_email ON public.users(email);
CREATE INDEX idx_users_role ON public.users(role);

-- ============================================================
-- RLS Policies
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Policy: User vê apenas próprio registro
CREATE POLICY users_view_own ON public.users
  FOR SELECT USING (id = auth.uid());

-- Policy: Admin vê todos os registros
CREATE POLICY users_admin_all ON public.users
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.users 
      WHERE id = auth.uid() AND role = 'admin'
    )
  );

-- ============================================================
-- Verificar tabela criada
-- ============================================================
SELECT 
  table_name, 
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE table_name = 'users';

-- Deve retornar: id, email, name, role, created_at
