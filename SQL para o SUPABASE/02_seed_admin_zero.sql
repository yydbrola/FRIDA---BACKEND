-- ============================================================
-- Seed: Admin Zero
-- ============================================================
-- 
-- INSTRUÇÕES:
-- 1. Acesse Supabase Dashboard → Authentication → Users → Add User
-- 2. Preencha:
--    - Email: admin@frida.com
--    - Password: (escolha uma senha segura)
--    - Auto Confirm User: ✓ (marcar)
-- 3. Clique "Create User"
-- 4. COPIE O UUID GERADO (ex: a1b2c3d4-e5f6-7890-abcd-ef1234567890)
-- 5. Substitua no INSERT abaixo e execute
-- 
-- ============================================================

INSERT INTO public.users (id, email, name, role)
VALUES (
  'COLE-SEU-UUID-AQUI',  -- ← COLAR UUID COPIADO DO AUTH
  'admin@frida.com',
  'Admin Zero',
  'admin'
);

-- Verificar inserção
SELECT * FROM public.users;

-- Deve retornar 1 linha com role = 'admin'
