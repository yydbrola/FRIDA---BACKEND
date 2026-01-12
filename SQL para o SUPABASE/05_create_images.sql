-- ============================================================
-- FRIDA: Tabela images
-- Executar no Supabase Dashboard → SQL Editor
-- Depende de: 01_create_users_table.sql, 04_create_products.sql
-- ============================================================

-- ============================================================
-- Criar tabela images
-- ============================================================
CREATE TABLE public.images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
  type TEXT CHECK (type IN ('original', 'segmented', 'processed')) NOT NULL,
  storage_bucket TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  quality_score INTEGER CHECK (quality_score >= 0 AND quality_score <= 100),
  created_by UUID REFERENCES public.users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================
-- Indexes para queries rápidas
-- ============================================================
CREATE INDEX idx_images_product_id ON public.images(product_id);
CREATE INDEX idx_images_created_by ON public.images(created_by);
CREATE INDEX idx_images_type ON public.images(type);

-- ============================================================
-- RLS Policies
-- ============================================================
ALTER TABLE public.images ENABLE ROW LEVEL SECURITY;

-- Policy: Member (role='user') - CRUD apenas em registros próprios
-- SELECT: ver apenas imagens que criou
CREATE POLICY images_member_select ON public.images
  FOR SELECT USING (
    created_by = auth.uid()
  );

-- INSERT: inserir apenas com created_by = próprio id
CREATE POLICY images_member_insert ON public.images
  FOR INSERT WITH CHECK (
    created_by = auth.uid()
  );

-- UPDATE: atualizar apenas imagens próprias
CREATE POLICY images_member_update ON public.images
  FOR UPDATE USING (
    created_by = auth.uid()
  );

-- DELETE: deletar apenas imagens próprias
CREATE POLICY images_member_delete ON public.images
  FOR DELETE USING (
    created_by = auth.uid()
  );

-- Policy: Admin (role='admin') - Acesso total
CREATE POLICY images_admin_all ON public.images
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
WHERE table_name = 'images';

-- Deve retornar: id, product_id, type, storage_bucket, storage_path, quality_score, created_by, created_at
