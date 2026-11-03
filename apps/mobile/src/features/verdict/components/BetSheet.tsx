import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { StyleSheet, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import type { VerdictSummary, YouState } from "@/domain/types";
import { useAuthStore } from "@/features/auth/authStore";
import { useCreateBetMutation, useDeleteBetMutation } from "@/features/records/queries";
import { useRestMutation } from "@/features/account/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useOddsFormat } from "@/features/preferences/prefsStore";
import { haptic } from "@/lib/haptics";
import { errorText, ApiError } from "@/lib/errors";
import { decimalToFormat, money, oddsFormatLabel, pickDirectionLabel } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Button, Chip, Sheet, Stepper, Text, useToast } from "@/components/ui";

interface BetSheetProps {
  visible: boolean;
  verdict: VerdictSummary | null;
  you: YouState | null;
  onClose: () => void;
  onRecorded: (betId: number) => void;
}

type Step = "amount" | "success" | "protection";

export function BetSheet({ visible, verdict, you, onClose, onRecorded }: BetSheetProps) {
  const [amount, setAmount] = useState(100);
  const [step, setStep] = useState<Step>("amount");
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [recordedAmount, setRecordedAmount] = useState<number | null>(null);
  const [undoDeadline, setUndoDeadline] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [protectionStreak, setProtectionStreak] = useState(0);
  const [alreadyRecorded, setAlreadyRecorded] = useState(false);
  const queryClient = useQueryClient();
  const createBet = useCreateBetMutation();
  const deleteBet = useDeleteBetMutation();
  const rest = useRestMutation();
  const { copy } = usePersonaContent();
  const oddsFormat = useOddsFormat();
  const toast = useToast();
  const session = useAuthStore((s) => s.session);

  useEffect(() => {
    if (!visible) return;
    setStep("amount");
    setCreatedId(null);
    setRecordedAmount(null);
    setUndoDeadline(0);
    setSecondsLeft(5);
    setError(null);
    setAlreadyRecorded(false);
    setProtectionStreak(0);
  }, [visible]);

  useEffect(() => {
    if (step !== "success" || !undoDeadline) return;
    const tick = () => {
      // 用绝对截止时间重算，App 退后台/JS 定时器被节流后不会显示虚假的剩余秒数。
      const left = Math.max(0, Math.ceil((undoDeadline - Date.now()) / 1000));
      setSecondsLeft(left);
    };
    tick();
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [step, undoDeadline]);

  if (!verdict) return null;
  const pickLabel = pickDirectionLabel(verdict.pool, verdict.pick?.dir);
  const sp = verdict.pick?.sp ?? verdict.sp.h;
  const spLabel = decimalToFormat(sp, oddsFormat);
  const formatLabel = oddsFormatLabel(oddsFormat);
  const ticketAmount = step === "success" ? recordedAmount ?? amount : amount;
  const ticket = `${verdict.matchNo} ${verdict.home} ${pickLabel} @${spLabel}（${formatLabel}） ×${ticketAmount}元`;

  const submit = async (confirm = false) => {
    if (!session) {
      setError("需要先连接服务端，拿到设备身份后才能记账。");
      return;
    }
    setError(null);
    try {
      const created = await createBet.mutateAsync({
        verdictId: verdict.id,
        amount,
        confirm,
      });
      setCreatedId(created.id);
      setRecordedAmount(created.amount ?? amount);
      setUndoDeadline(Date.now() + 5000);
      setStep("success");
      setSecondsLeft(5);
      haptic("success");
      onRecorded(created.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 423) {
        const body = (e.detail ?? {}) as { detail?: { streak?: number }; streak?: number };
        const detail = body.detail ?? body;
        setProtectionStreak(typeof detail.streak === "number" ? detail.streak : you?.streak ?? 0);
        setStep("protection");
        return;
      }
      if (e instanceof ApiError && e.status === 409) {
        setAlreadyRecorded(true);
        setError("这注已经记过了，不用重复记。");
        void queryClient.invalidateQueries({ queryKey: ["bets"] });
        return;
      }
      setError(errorText(e));
      haptic("error");
    }
  };

  const undo = async () => {
    if (!createdId) return;
    try {
      await deleteBet.mutateAsync(createdId);
      haptic("warning");
      toast.show("已撤销，这注没有入账", "info");
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const copyTicket = async () => {
    await Clipboard.setStringAsync(ticket);
    haptic("light");
    toast.show("出票文案已复制", "success");
  };

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      title={step === "success" ? "已记下" : step === "protection" ? "连败保护已触发" : "记一注"}
      subtitle={
        step === "success"
          ? secondsLeft > 0
            ? `${secondsLeft} 秒内可以撤销。`
            : "已入账。中间不用再看了。"
          : step === "protection"
            ? "不是拦你，是提醒你在低谷别加注。"
            : "只记账，不代购。金额只有你自己看得到。"
      }
      footer={
        step === "amount" ? (
          <Button
            label={createBet.isPending ? "正在入账…" : `确认记 ${money(amount)}`}
            onPress={() => submit(false)}
            loading={createBet.isPending}
            disabled={!session || alreadyRecorded}
            fullWidth
          />
        ) : step === "success" ? (
          <Button
            label={secondsLeft > 0 ? `撤销（${secondsLeft}s）` : "完成"}
            variant={secondsLeft > 0 ? "secondary" : "primary"}
            onPress={secondsLeft > 0 ? undo : onClose}
            fullWidth
            loading={deleteBet.isPending}
          />
        ) : (
          <View style={{ gap: spacing.sm }}>
            <Button label="我确认，继续记" onPress={() => submit(true)} loading={createBet.isPending} fullWidth />
            <Button
              label="先休息，今晚不记了"
              variant="secondary"
              onPress={async () => {
                try {
                  await rest.mutateAsync(true);
                  toast.show("好，今晚先到这里", "success");
                  onClose();
                } catch (e) {
                  toast.show(errorText(e), "error");
                }
              }}
              fullWidth
            />
          </View>
        )
      }
    >
      {step === "amount" ? (
        <>
          <View style={styles.matchBox}>
            <Text variant="caption" color={colors.muted}>{verdict.matchNo} · {verdict.home} vs {verdict.away}</Text>
            <Text variant="h3" style={styles.pick}>
              {pickLabel} <Text variant="caption" color={colors.muted}>@ {spLabel} · {formatLabel}</Text>
            </Text>
            <Text variant="caption" color={colors.green}>三关全过 · 抽水 {(Number(verdict.rake ?? 0) * 100).toFixed(1)}%</Text>
          </View>

          <Stepper value={amount} onChange={(next) => { if (!createBet.isPending) setAmount(next); }}
                   min={10} max={100000} step={10} />
          <View style={styles.quick}>
            {[50, 100, 200, 500].map((value) => (
              <Chip key={value} label={`¥${value}`} selected={amount === value}
                    onPress={() => { if (!createBet.isPending) setAmount(value); }} />
            ))}
          </View>
          <Button label="复制出票文案" variant="ghost" size="sm" icon="copy-outline" onPress={copyTicket} />
          {you?.protectionActive ? (
            <Text variant="caption" color={colors.amber} style={styles.note}>
              {copy.protection(you.streak)}
            </Text>
          ) : null}
          {error ? <Text variant="caption" color={colors.danger}>{error}</Text> : null}
        </>
      ) : step === "success" ? (
        <>
          <View style={styles.successBox}>
            <Text variant="h2">{money(recordedAmount ?? amount)}</Text>
            <Text variant="small" color={colors.muted}>{pickLabel} · {verdict.matchNo}</Text>
          </View>
          <Text variant="small" color={colors.ink} style={styles.note}>{copy.comfort}</Text>
          <Button label="复制出票文案" variant="secondary" size="sm" icon="copy-outline" onPress={copyTicket} />
          {error ? <Text variant="caption" color={colors.danger}>{error}</Text> : null}
        </>
      ) : (
        <>
          <Text variant="body" color={colors.ink} style={styles.note}>
            你已连败 {protectionStreak || you?.streak || 0} 场。低谷加注是亏损扩大的最常见方式。
          </Text>
          <Text variant="small" color={colors.muted} style={styles.note}>
            继续记仍然可以，但请确认这是你冷静后的决定；也可以先休息，明天再看。
          </Text>
          {error ? <Text variant="caption" color={colors.danger}>{error}</Text> : null}
        </>
      )}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  matchBox: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.base,
    gap: 3,
    marginBottom: spacing.base,
  },
  pick: { marginTop: 2 },
  quick: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginVertical: spacing.base },
  note: { lineHeight: 20, marginBottom: spacing.sm },
  successBox: {
    alignItems: "center",
    gap: 2,
    backgroundColor: colors.greenSoft,
    borderRadius: radii.md,
    paddingVertical: spacing.xl,
    marginBottom: spacing.base,
  },
});
