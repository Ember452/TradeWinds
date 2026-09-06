import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Sailboat, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/shared/auth";
import { ApiError } from "@/shared/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const DEMO_EMAIL = "demo@tradewinds.local";
const DEMO_PASSWORD = "demo12345";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      navigate("/topics");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "网络错误,请稍后再试");
    } finally {
      setSubmitting(false);
    }
  }

  function fillDemo() {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    setError(null);
    toast.info("已填充演示账号,点击登录即可");
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* 左侧:晴空插画层 */}
      <div
        className="relative hidden flex-col justify-between overflow-hidden p-10 lg:flex"
        style={{ background: "linear-gradient(180deg, var(--c-sky-1) 0%, var(--c-sky-2) 55%, var(--c-sky-3) 100%)" }}
      >
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(circle at 75% 18%, rgba(255,240,190,.5), transparent 45%)" }}
        />
        <motion.div
          className="relative"
          initial={reduce ? false : { x: -60, y: 40, rotate: 8 }}
          animate={reduce ? undefined : { x: [0, 24, 0], y: [0, -12, 0], rotate: [0, -4, 0] }}
          transition={reduce ? undefined : { duration: 12, repeat: Infinity, ease: "easeInOut" }}
        >
          <svg viewBox="0 0 24 24" className="size-24 drop-shadow-lg">
            <path d="M2 12 L22 3 L15 21 L11 14 Z" fill="#fff" stroke="rgba(30,60,120,.85)" strokeWidth="1" strokeLinejoin="round" />
          </svg>
        </motion.div>
        <div className="relative text-white">
          <span className="flex items-center gap-2 text-lg font-bold drop-shadow">
            <Sailboat className="size-5" /> TradeWinds
          </span>
          <p className="mt-3 max-w-sm text-2xl font-extrabold leading-snug drop-shadow-md">
            让纸飞机替你飞遍技术的天空
          </p>
          <p className="mt-2 max-w-sm text-sm text-white/85">
            订阅主题,情报自动飞进你的信箱。
          </p>
        </div>
      </div>

      {/* 右侧:表单 */}
      <div className="flex items-center justify-center p-6">
        <Card className="w-full max-w-md shadow-xl">
          <CardHeader>
            <CardTitle className="text-2xl">{isRegister ? "注册 TradeWinds" : "登录 TradeWinds"}</CardTitle>
            <CardDescription>
              {isRegister ? "创建账号,开始你的第一份情报简报" : "欢迎回来,情报正在路上"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">邮箱</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="password">密码{isRegister && "(至少 8 位)"}</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  placeholder="••••••••"
                />
              </div>
              {error && (
                <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "提交中…" : isRegister ? "注册并登录" : "登录"}
              </Button>
              {!isRegister && (
                <Button type="button" variant="ghost" onClick={fillDemo} className="text-muted-foreground">
                  <Wand2 className="size-4" /> 一键填充演示账号
                </Button>
              )}
            </form>
            <p className="mt-5 text-center text-sm text-muted-foreground">
              {isRegister ? (
                <>
                  已有账号?<Link to="/login" className="font-semibold text-primary hover:underline">去登录</Link>
                </>
              ) : (
                <>
                  没有账号?<Link to="/register" className="font-semibold text-primary hover:underline">注册</Link>
                </>
              )}
              <span className="mx-1.5">·</span>
              <Link to="/" className="hover:text-foreground">返回首页</Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
