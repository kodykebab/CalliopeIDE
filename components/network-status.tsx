"use client";

import React, { useEffect, useState } from 'react';
import { Activity, CloudOff } from 'lucide-react';
import { cn } from "@/lib/utils";

export function NetworkStatus({ className }: { className?: string }) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        // Stellar Testnet Horizon API'sine kısa bir istek atıyoruz
        const response = await fetch('https://horizon-testnet.stellar.org/', { 
          method: 'HEAD',
          cache: 'no-store' 
        });
        setIsOnline(response.ok);
      } catch (error) {
        setIsOnline(false);
      }
    };

    // İlk açılışta kontrol et
    checkStatus();
    
    // Her 30 saniyede bir otomatik güncelle
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Veri gelene kadar (loading) boş görünmesin diye null kontrolü
  if (isOnline === null) return (
    <div className="flex items-center gap-2 px-3 h-10 rounded-full border border-border/40 bg-background/50 animate-pulse">
      <div className="h-2 w-2 rounded-full bg-gray-400" />
      <span className="text-[10px] text-muted-foreground uppercase tracking-widest">Checking...</span>
    </div>
  );

  return (
    <div 
      className={cn(
        "flex items-center gap-2 px-3 h-10 rounded-full border border-border/80 bg-background/75 text-[10px] font-bold shadow-sm backdrop-blur-sm transition-all duration-500",
        isOnline ? "hover:border-green-500/50" : "hover:border-red-500/50",
        className
      )}
    >
      {/* Sinyal Işığı (Pulse Animasyonlu) */}
      <div className="relative flex h-2 w-2">
        {isOnline && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
        )}
        <span className={cn(
          "relative inline-flex rounded-full h-2 w-2 transition-colors duration-500",
          isOnline ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"
        )}></span>
      </div>
      
      {/* Yazı ve İkon Kısmı */}
      <span className="text-foreground/90 uppercase tracking-widest flex items-center gap-1.5 pointer-events-none">
        {isOnline ? (
          <>
            <Activity className="size-3 text-green-500" /> 
            <span>Stellar Online</span>
          </>
        ) : (
          <>
            <CloudOff className="size-3 text-red-500" /> 
            <span>Stellar Offline</span>
          </>
        )}
      </span>
    </div>
  );
}
