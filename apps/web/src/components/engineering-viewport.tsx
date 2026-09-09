'use client';

import { Canvas } from '@react-three/fiber';
import { useMemo } from 'react';

type GeometryKind = 'EDF' | 'Aircraft' | 'Turbine';

function Rotor({ kind }: { kind: GeometryKind }) {
  const blades = useMemo(() => Array.from({ length: kind === 'Turbine' ? 11 : 8 }, (_, index) => index), [kind]);
  if (kind === 'Aircraft') return <group rotation={[-0.25, 0.45, 0]}><mesh><boxGeometry args={[4.8, 0.14, 0.7]} /><meshStandardMaterial color="#91a9bd" metalness={0.65} roughness={0.32} /></mesh><mesh position={[0.1, 0.22, 0]} rotation={[0, 0, 0.1]}><boxGeometry args={[1.7, 0.18, 3.8]} /><meshStandardMaterial color="#b7c7d6" metalness={0.55} roughness={0.35} /></mesh><mesh position={[-1.9, 0.12, 0]}><coneGeometry args={[0.45, 1.2, 16]} rotation={[0, 0, -Math.PI / 2]} /><meshStandardMaterial color="#536b80" metalness={0.75} roughness={0.26} /></mesh></group>;
  return <group rotation={[0.25, -0.55, 0]}><mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.85, 0.16, 16, 64]} /><meshStandardMaterial color="#758da3" metalness={0.75} roughness={0.23} /></mesh><mesh rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.58, 0.58, 1.7, 32]} /><meshStandardMaterial color="#2b3e50" metalness={0.85} roughness={0.22} /></mesh>{blades.map((blade) => <mesh key={blade} rotation={[0, 0, blade * (Math.PI * 2 / blades.length)]}><boxGeometry args={[0.16, 1.65, 0.09]} /><meshStandardMaterial color={kind === 'Turbine' ? '#c9904e' : '#8ec0d7'} metalness={0.7} roughness={0.28} /></mesh>)}</group>;
}

export default function EngineeringViewport({ shape }: { shape: GeometryKind }) {
  return <div className="canvas-wrap" role="img" aria-label={`${shape} analytical geometry preview`}><Canvas camera={{ position: [5.5, 3.5, 6.2], fov: 35 }} dpr={[1, 1.5]} frameloop="demand" gl={{ antialias: true, alpha: true }}><color attach="background" args={['#0d1620']} /><ambientLight intensity={0.55} /><directionalLight position={[5, 6, 4]} intensity={2.1} color="#c8efff" /><pointLight position={[-4, -1, 3]} intensity={8} color="#126b91" /><Rotor kind={shape} /><gridHelper args={[12, 18, '#244152', '#182a38']} position={[0, -2.25, 0]} /></Canvas><div className="axis axis-x" aria-hidden="true">X</div><div className="axis axis-y" aria-hidden="true">Y</div><div className="axis axis-z" aria-hidden="true">Z</div></div>;
}
