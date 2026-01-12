-- ============================================================
-- FRIDA: Tabela products
-- Executar no Supabase Dashboard → SQL Editor
-- Depende de: 01_create_users_table.sql (users table)
-- ============================================================

-- ============================================================
-- Criar tabela products
-- ============================================================
CREATE TABLE public.products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sku TEXT UNIQUE,
  category TEXT,
  classification_result JSONB,  -- Stores Gemini API classification response
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'published')) NOT NULL,
  created_by UUID REFERENCES public.users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================
-- Indexes para queries rápidas
-- ============================================================
CREATE INDEX idx_products_created_by ON public.products(created_by);
CREATE INDEX idx_products_status ON public.products(status);
CREATE INDEX idx_products_category ON public.products(category);
CREATE INDEX idx_products_sku ON public.products(sku);

-- ============================================================
-- Trigger para updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER products_updated_at
  BEFORE UPDATE ON public.products
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- RLS Policies
-- ============================================================
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;

-- Policy: Member (role='user') - CRUD apenas em registros próprios
-- SELECT: ver apenas produtos que criou
CREATE POLICY products_member_select ON public.products
  FOR SELECT USING (
    created_by = auth.uid()
  );

-- INSERT: inserir apenas com created_by = próprio id
CREATE POLICY products_member_insert ON public.products
  FOR INSERT WITH CHECK (
    created_by = auth.uid()
  );

-- UPDATE: atualizar apenas produtos próprios
CREATE POLICY products_member_update ON public.products
  FOR UPDATE USING (
    created_by = auth.uid()
  );

-- DELETE: deletar apenas produtos próprios
CREATE POLICY products_member_delete ON public.products
  FOR DELETE USING (
    created_by = auth.uid()
  );

-- Policy: Admin (role='admin') - Acesso total
CREATE POLICY products_admin_all ON public.products
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
WHERE table_name = 'products';

-- Deve retornar: id, name, sku, category, classification_result, status, created_by, created_at, updated_at
