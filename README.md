# Implementare Switch cu VLAN și Spanning Tree Protocol (STP)

## Obreja Ana-Maria 331CA, noiembrie 2024

Codul este conceput pentru a simula un switch care implementează funcționalități 
de VLAN și Spanning Tree Protocol (STP), respectând principiile de control al 
buclelor și de comutare VLAN.

1. **Structura Generală**:
   Codul include două tabele principale - `mac_table` și `vlan_table`, ambele 
   implementate ca dicționare. `mac_table` asociază adresele MAC sursă 
   cu interfețele de intrare, iar `vlan_table` asociază VLAN-urile specifice 
   cu interfețele configurate

2. **Procesarea BPDU-urilor pentru STP**:
   Codul implementează logica BPDU (Bridge Protocol Data Unit) pentru STP, 
   inițializând fiecare switch ca root bridge. La recepționarea BPDU-urilor, 
   codul compară `root_bridge_id` din pachetul primit cu cel al switch-ului 
   curent. Dacă noul `root_bridge_id` este mai mic, switch-ul își actualizează 
   root-ul și recalculează costurile către acesta. Această structură asigură că 
   switch-ul poate bloca legăturile care pot crea bucle.

3. **Actualizarea Statutului Porturilor**:
   Funcția `process_bpdu` controlează comportamentul porturilor de tip trunk 
   și gestionează trecerea lor între stările `FORWARDING` și `BLOCKING`. 
   Structura porturilor și stările lor sunt organizate într-un dicționar, 
   `port_states`, pentru acces facil și actualizări rapide. Prin această 
   structură, codul monitorizează activ toate porturile trunk și le blochează 
   temporar, exceptând root-ul, atunci când switch-ul este root bridge. 
   Pentru a putea diferenția ușor porturile trunk de cele access m-am folosit
   de lista `trunk_ports` cu indicii porturilor care sunt de tip trunk.

4. **Tagging VLAN și Comutare**:
   În logica de comutare a pachetelor, codul verifică dacă un pachet necesită 
   un tag VLAN înainte de a fi transmis printr-un port trunk. Dacă un pachet 
   vine fără tag și urmează să fie transmis printr-un port trunk, i se adaugă 
   un tag VLAN specific interfeței sursă. În cazul porturilor access, codul 
   elimină tag-ul VLAN atunci când cadrul este destinat unui host. Această 
   secțiune permite compatibilitatea cu configurarea VLAN-urilor și asigură 
   că doar cadrele corespunzătoare unui VLAN sunt trimise către porturile 
   relevante.

5. **Componentele de Configurație**:
   Funcția `read_configs` este utilizată pentru a citi fișierele de 
   configurare specifice fiecărui switch. Aceasta setează prioritățile 
   bridge-ului, configurează VLAN-urile și identifică porturile trunk. Pentru
   porturile trunk, VLAN-ul este setat pe -1 si configurat dupa ce primim
   pachetul, in timp ce pentru pachetele primite de pe porturi de tip access
   (care vin cu VLAN-ul codul -1), aflam VLAN-ul din tabela `vlan_table`,
   cu indexul interfetei pe care a fost primit.
