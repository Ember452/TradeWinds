import { motion, useReducedMotion } from "framer-motion";
import { ChevronDown, Sailboat } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const PLANE_PATH = "M2 12 L22 3 L15 21 L11 14 Z";

// 纸飞机:外层绕轨道公转,内层反向自转保持机头朝向
function OrbitPlane({ radius, duration, size, reverse = false }: { radius: number; duration: number; size: number; reverse?: boolean }) {
  const reduce = useReducedMotion();
  const spin = reverse ? -360 : 360;
  return (
    <motion.div
      className="pointer-events-none absolute left-1/2 top-1/2"
      style={{ width: 0, height: 0 }}
      animate={reduce ? undefined : { rotate: [0, spin] }}
      transition={{ duration, repeat: Infinity, ease: "linear" }}
    >
      <motion.svg
        viewBox="0 0 24 24"
        style={{ width: size, height: size, x: radius / 2, y: -size / 2, filter: "drop-shadow(0 0 10px rgba(255,255,255,.55))" }}
        animate={reduce ? undefined : { rotate: [0, -spin] }}
        transition={{ duration, repeat: Infinity, ease: "linear" }}
      >
        <path d={PLANE_PATH} fill="#fff" stroke="rgba(30,60,120,.85)" strokeWidth="1.2" strokeLinejoin="round" />
      </motion.svg>
    </motion.div>
  );
}

// 流云:横向缓慢漂移的长条
function Cloud({ top, width, duration, delay = 0, opacity }: { top: string; width: number; duration: number; delay?: number; opacity: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="pointer-events-none absolute rounded-full bg-white blur-[2px]"
      style={{ top, width, height: width / 3.4, opacity }}
      initial={{ x: "-20vw" }}
      animate={reduce ? { x: "30vw" } : { x: "110vw" }}
      transition={{ duration, repeat: Infinity, ease: "linear", delay }}
    />
  );
}

export function Hero() {
  const reduce = useReducedMotion();

  return (
    <section className="relative flex min-h-[92vh] flex-col overflow-hidden">
      {/* 天空:深空到晨光的三段渐变 + 体积光斑 */}
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg, var(--c-sky-1) 0%, var(--c-sky-2) 55%, var(--c-sky-3) 100%)" }}
      />
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(circle at 78% 16%, rgba(255,240,190,.5), transparent 42%)" }}
      />

      <Cloud top="16%" width={110} duration={22} opacity={0.9} />
      <Cloud top="30%" width={70} duration={30} delay={6} opacity={0.7} />
      <Cloud top="9%" width={150} duration={38} delay={12} opacity={0.75} />

      {/* 中央动效组:情报核心 + 双纸飞机轨道 */}
      <div className="relative mx-auto mt-[16vh] flex w-full max-w-3xl flex-col items-center px-4 text-center">
        <div className="relative mb-10 h-52 w-52">
          <div className="absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-white/50" />
          <OrbitPlane radius={216} duration={8} size={30} />
          <OrbitPlane radius={150} duration={13} size={20} reverse />
          <motion.div
            className="absolute left-1/2 top-1/2 flex size-24 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-3xl border border-white/40 bg-white/15 shadow-2xl backdrop-blur-md"
            animate={reduce ? undefined : { y: [0, -8, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            <Sailboat className="size-11 text-white drop-shadow-lg" />
          </motion.div>
        </div>

        <motion.h1
          className="text-balance text-4xl font-extrabold leading-tight text-white drop-shadow-md sm:text-5xl"
          initial={reduce ? false : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          让纸飞机替你飞遍技术的天空
        </motion.h1>
        <motion.p
          className="mt-4 text-base text-white/90 drop-shadow sm:text-lg"
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15, ease: "easeOut" }}
        >
          订阅主题 · 多源检索 · AI 评分聚类 · 每日情报送达
        </motion.p>

        <motion.div
          className="mt-8 flex flex-wrap items-center justify-center gap-3"
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease: "easeOut" }}
        >
          <Button asChild size="lg" className="h-11 bg-accent px-7 text-base font-semibold text-accent-foreground shadow-lg hover:bg-accent/90">
            <Link to="/register">免费开始</Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="outline"
            className="h-11 border-white/60 bg-white/10 px-7 text-base text-white backdrop-blur hover:bg-white/20 hover:text-white"
          >
            <Link to="/share/reports/mock-share-token">查看示例报告</Link>
          </Button>
        </motion.div>
      </div>

      <motion.div
        className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/85"
        animate={reduce ? undefined : { y: [0, 8, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      >
        <ChevronDown className="size-7" />
      </motion.div>
    </section>
  );
}
