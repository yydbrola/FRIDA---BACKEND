-- ============================================================
-- FRIDA: RLS Policies Dual Mode (Dev + Prod)
-- Executar no Supabase Dashboard → SQL Editor
-- Depende de: 01_create_users_table.sql, 04_create_products.sql, 05_create_images.sql
-- ============================================================
-- 
-- Estas policies funcionam em:
-- - Dev: service_role bypassa RLS automaticamente
-- - Prod: JWT auth com verificação de ownership/role
--
-- Regras:
-- - Member: vê/edita apenas registros onde created_by = auth.uid()
-- - Admin: vê/edita todos os registros
-- ============================================================


-- ============================================================
-- PRODUCTS TABLE - RLS POLICIES
-- ============================================================

-- Dropar policies antigas (se existirem)
DROP POLICY IF EXISTS "products_member_isolation" ON products;
DROP POLICY IF EXISTS "products_admin_all" ON products;
DROP POLICY IF EXISTS "products_select_policy" ON products;
DROP POLICY IF EXISTS "products_insert_policy" ON products;
DROP POLICY IF EXISTS "products_update_policy" ON products;
DROP POLICY IF EXISTS "products_delete_policy" ON products;
DROP POLICY IF EXISTS "products_member_select" ON products;
DROP POLICY IF EXISTS "products_member_insert" ON products;
DROP POLICY IF EXISTS "products_member_update" ON products;
DROP POLICY IF EXISTS "products_member_delete" ON products;
DROP POLICY IF EXISTS "products_dev_all" ON products;
DROP POLICY IF EXISTS "products_service_role_bypass" ON products;

-- Ativar RLS
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- SELECT: Member vê próprios, Admin vê todos
CREATE POLICY "products_select_policy" ON products
FOR SELECT USING (
    auth.uid() IS NOT NULL AND (
        created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);

-- INSERT: created_by deve ser auth.uid()
CREATE POLICY "products_insert_policy" ON products
FOR INSERT WITH CHECK (
    auth.uid() IS NOT NULL AND created_by = auth.uid()
);

-- UPDATE: Member edita próprios, Admin edita todos
CREATE POLICY "products_update_policy" ON products
FOR UPDATE USING (
    auth.uid() IS NOT NULL AND (
        created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);

-- DELETE: Member deleta próprios apenas em draft, Admin deleta todos
CREATE POLICY "products_delete_policy" ON products
FOR DELETE USING (
    auth.uid() IS NOT NULL AND (
        (created_by = auth.uid() AND status = 'draft')
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);


-- ============================================================
-- IMAGES TABLE - RLS POLICIES
-- ============================================================

-- Dropar policies antigas (se existirem)
DROP POLICY IF EXISTS "images_member_isolation" ON images;
DROP POLICY IF EXISTS "images_admin_all" ON images;
DROP POLICY IF EXISTS "images_select_policy" ON images;
DROP POLICY IF EXISTS "images_insert_policy" ON images;
DROP POLICY IF EXISTS "images_update_policy" ON images;
DROP POLICY IF EXISTS "images_delete_policy" ON images;
DROP POLICY IF EXISTS "images_member_select" ON images;
DROP POLICY IF EXISTS "images_member_insert" ON images;
DROP POLICY IF EXISTS "images_member_update" ON images;
DROP POLICY IF EXISTS "images_member_delete" ON images;
DROP POLICY IF EXISTS "images_dev_all" ON images;
DROP POLICY IF EXISTS "images_service_role_bypass" ON images;

-- Ativar RLS
ALTER TABLE images ENABLE ROW LEVEL SECURITY;

-- SELECT: Member vê próprias, Admin vê todas
CREATE POLICY "images_select_policy" ON images
FOR SELECT USING (
    auth.uid() IS NOT NULL AND (
        created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);

-- INSERT: verifica ownership do produto
CREATE POLICY "images_insert_policy" ON images
FOR INSERT WITH CHECK (
    auth.uid() IS NOT NULL 
    AND created_by = auth.uid()
    AND (
        EXISTS (SELECT 1 FROM products WHERE products.id = product_id AND products.created_by = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);

-- UPDATE: Member edita próprias, Admin edita todas
CREATE POLICY "images_update_policy" ON images
FOR UPDATE USING (
    auth.uid() IS NOT NULL AND (
        created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);

-- DELETE: Member deleta próprias, Admin deleta todas
CREATE POLICY "images_delete_policy" ON images
FOR DELETE USING (
    auth.uid() IS NOT NULL AND (
        created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.role = 'admin')
    )
);


-- ============================================================
-- GRANTS para roles
-- ============================================================

-- service_role precisa de GRANT explícito (não herda automaticamente)
GRANT ALL ON products TO service_role;
GRANT ALL ON products TO authenticated;
GRANT SELECT ON products TO anon;

GRANT ALL ON images TO service_role;
GRANT ALL ON images TO authenticated;
GRANT SELECT ON images TO anon;


-- ============================================================
-- Verificar policies criadas
-- ============================================================
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    cmd
FROM pg_policies 
WHERE tablename IN ('products', 'images')
ORDER BY tablename, policyname;

-- Deve retornar 8 policies (4 para products, 4 para images)
