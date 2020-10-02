from lb_main import BusData, BranchData, TransformerData
from datetime import datetime
from lb_psse import psseCalc, Text_logger
import networkx as nx
import matplotlib.pyplot as plt

filename = r'C:\Users\marecekt\PycharmProjects\LF_check\data\20200904_1445_SN5_CZ0.raw'
filename2 = r'C:\Users\marecekt\PycharmProjects\LF_check\data\20200904_1445_SN5_CZ0_cal.raw'
config_file = r'C:\Users\marecekt\PycharmProjects\LF_check\raw_exp_obj.cfg'
coordination_file = r'C:\Users\marecekt\PycharmProjects\LF_check\souradnice_rozvoden.csv'


def calculate_grid(busdata, branchdata, transformerdata, busdata_2):
    calculated_connections, start_busnumbers, skipped_connections = [], [], {}
    # graph
    G = nx.DiGraph()
    edge_labels = {}
    # beginning of the calculation
    slackbus = busdata.get_slack_bus()
    start_busnumbers.append(slackbus)
    while start_busnumbers:
        end_busnumbers = []
        for start_busnumber in start_busnumbers:
            branch_connections = branchdata.get_connections_of_busnumber(start_busnumber.busnumber)
            # calculate power for every connection
            for branch in branch_connections:
                firstbus = busdata.get_bus_data(start_busnumber.busnumber)  # start bus
                firstbus_2 = busdata_2.get_bus_data(start_busnumber.busnumber)  # start bus
                secondbus = busdata.get_bus_data(branch.busnumber2)  # end bus
                secondbus_2 = busdata_2.get_bus_data(branch.busnumber2)  # end bus
                # skip already calculated
                if (str(branch.busnumber1) + '-' + str(branch.busnumber2) + '-' + str(branch.ckt) in
                        calculated_connections or str(branch.busnumber2) + '-' + str(branch.busnumber1) + '-' +
                        str(branch.ckt) in calculated_connections):
                    continue
                else:
                    P_1 = branchdata.calculate_power(firstbus.vm, firstbus.va, secondbus.vm, secondbus.va, branch.r,
                                                     branch.x, branch.b)
                    if P_1 != 0:
                        P_2 = branchdata.calculate_power(firstbus_2.vm, firstbus_2.va, secondbus_2.vm, secondbus_2.va,
                                                         branch.r, branch.x, branch.b)
                        P = P_1 - P_2
                    # No power flow for calculated between buses in the first file
                    else:
                        busnumber_not_found = True
                        # check if busnumber already in values
                        for key, values in skipped_connections.iteritems():
                            for value in values:
                                if firstbus.trisname == value and secondbus.trisname not in values:
                                    skipped_connections[key].append(secondbus.trisname)
                                    busnumber_not_found = False
                                elif firstbus.trisname == value:
                                    busnumber_not_found = False
                        # new key
                        if busnumber_not_found:
                            if firstbus.trisname not in skipped_connections.keys():
                                skipped_connections[firstbus.trisname] = [secondbus.trisname]
                            # add to key
                            else:
                                skipped_connections[firstbus.trisname].append(secondbus.trisname)
                        calculated_connections.append(str(firstbus.busnumber) + '-' + str(secondbus.busnumber) + '-' +
                                                      str(branch.ckt))
                        end_busnumbers.append(secondbus)
                        continue
                    calculated_connections.append(str(firstbus.busnumber) + '-' + str(secondbus.busnumber) + '-'
                                                  + str(branch.ckt))
                    end_busnumbers.append(secondbus)
                    # add to graph
                    if start_busnumber.basekv == 400.0:
                        color = 'y'
                    elif start_busnumber.basekv == 220.0:
                        color = 'r'
                    else:
                        color = 'g'
                    if abs(P) > 20.0:
                        weight = 6
                    elif abs(P) > 5.0:
                        weight = 3
                    else:
                        weight = 1
                    # Check for skipped connections
                    busnumber_not_found = True
                    for key, values in skipped_connections.iteritems():
                        for value in values:
                            if firstbus.trisname == value:
                                if firstbus.basekv == 400.0 or firstbus.basekv == 220.0:
                                    fixed_coordinations[firstbus.trisname] = (
                                        busdata.get_coordination(firstbus.name, coordination_file))
                                    fixed_coordinations[secondbus.trisname] = (
                                        busdata.get_coordination(secondbus.name, coordination_file))
                                    G.add_edge(key, secondbus.trisname, color=color, weight=weight)
                                    edge_labels[(key, secondbus.trisname)] = round(P, 2)
                                busnumber_not_found = False
                    if busnumber_not_found:
                        if firstbus.basekv == 400.0 or firstbus.basekv == 220.0:
                            fixed_coordinations[firstbus.trisname] = (
                                busdata.get_coordination(firstbus.name, coordination_file))
                            fixed_coordinations[secondbus.trisname] = (
                                busdata.get_coordination(secondbus.name, coordination_file))
                            G.add_edge(firstbus.trisname, secondbus.trisname, color=color, weight=weight)
                            edge_labels[(firstbus.trisname, secondbus.trisname)] = round(P, 2)
            # connections of transformers
            transfomer_connections = transformerdata.get_connections_of_busnumber(start_busnumber.busnumber)
            for transformer in transfomer_connections:
                firstbus = busdata.get_bus_data(transformer.busnumber1)  # higher voltage
                firstbus_2 = busdata_2.get_bus_data(transformer.busnumber1)  # higher voltage
                secondbus = busdata.get_bus_data(transformer.busnumber2)  # lower voltage
                secondbus_2 = busdata_2.get_bus_data(transformer.busnumber2)  # lower voltage
                if firstbus.basekv < secondbus.basekv:
                    firstbus = busdata.get_bus_data(transformer.busnumber2)  # higher voltage
                    firstbus_2 = busdata_2.get_bus_data(transformer.busnumber2)  # higher voltage
                    secondbus = busdata.get_bus_data(transformer.busnumber1)  # lower voltage
                    secondbus_2 = busdata_2.get_bus_data(transformer.busnumber1)  # lower voltage
                # skip already calculated
                if (str(transformer.busnumber1) + '-' + str(transformer.busnumber2) + '-' + str(transformer.ckt)
                        in calculated_connections or str(transformer.busnumber2) + '-' + str(transformer.busnumber1)
                        + '-' + str(transformer.ckt) in calculated_connections):
                    continue
                else:
                    P_1 = transformerdata.calculate_power(firstbus.vm, firstbus.va, secondbus.vm, secondbus.va,
                                                          transformer.Pk, transformer.P0, transformer.uk,
                                                          transformer.I0, transformer.Sn, firstbus.basekv,
                                                          secondbus.basekv, transformer.V_prim, transformer.V_sek,
                                                          transformer.V_sek_nom)
                    P_2 = transformerdata.calculate_power(firstbus_2.vm, firstbus_2.va, secondbus_2.vm, secondbus_2.va,
                                                          transformer.Pk, transformer.P0, transformer.uk,
                                                          transformer.I0, transformer.Sn, firstbus.basekv,
                                                          secondbus.basekv, transformer.V_prim, transformer.V_sek,
                                                          transformer.V_sek_nom)
                    P = P_1 - P_2
                    calculated_connections.append(str(firstbus.busnumber) + '-' + str(secondbus.busnumber) + '-'
                                                  + str(transformer.ckt))
                    end_busnumbers.append(secondbus)
                    if abs(P) > 20.0:
                        weight = 6
                    elif abs(P) > 5.0:
                        weight = 3
                    else:
                        weight = 1
                    busnumber_not_found = True
                    for key, values in skipped_connections.iteritems():
                        for value in values:
                            if firstbus.trisname == value:
                                if secondbus.basekv == 400.0 or secondbus.basekv == 220.0:
                                    fixed_coordinations[firstbus.trisname] = (
                                        busdata.get_coordination(firstbus.name, coordination_file))
                                    fixed_coordinations[secondbus.trisname] = (
                                        busdata.get_coordination(secondbus.name, coordination_file))
                                    G.add_edge(key, secondbus.trisname, color='black', weight=weight)
                                    edge_labels[(key, secondbus.trisname)] = round(P, 2)
                                busnumber_not_found = False
                        if busnumber_not_found:
                            if secondbus.basekv == 400.0 or secondbus.basekv == 220.0:
                                fixed_coordinations[firstbus.trisname] = (
                                    busdata.get_coordination(firstbus.name, coordination_file))
                                fixed_coordinations[secondbus.trisname] = (
                                    busdata.get_coordination(secondbus.name, coordination_file))
                                G.add_edge(firstbus.trisname, secondbus.trisname, color='black', weight=weight)
                                edge_labels[(firstbus.trisname, secondbus.trisname)] = round(P, 2)
        # continue in grid
        start_busnumbers = end_busnumbers
    return G, edge_labels

def create_graph(G, edge_labels):
    plt.figure(figsize=(16, 16))
    # pos = nx.spring_layout(G)
    pos = fixed_coordinations
    edges = G.edges()
    # colors = [G[u][v]['color'] for u, v in edges]
    # weights = [G[u][v]['weight'] for u, v in edges]
    # nx.draw(G, pos, node_size=200, font_size=6, node_color='pink', alpha=0.5, edge_color=colors, width=weights,
    #         labels={node: node for node in G.nodes()})
    nx.draw(G, pos, node_size=200, font_size=6, node_color='pink', alpha=0.5, labels={node: node for node in G.nodes()})
    nx.draw_networkx_edge_labels(G, pos, font_size=6, edge_labels=edge_labels, font_color='black')
    plt.savefig("plot.png", dpi=300)


if __name__ == '__main__':
    mylog = Text_logger(datetime.now(), 'LF_check')
    logger = mylog.logger
    fixed_coordinations = {}
    # psseCalc = psseCalc()
    # psseCalc.psse_init(logger)
    # psseCalc.load_model_raw(filename, logger)
    # psseCalc.dis_isl(logger)
    # psseCalc.calculate_nr(filename, logger)
    # psseCalc.save_raw32(filename2, logger)

    # Parse data of the First and the Second file
    busdata = BusData(filename, config_file)
    branchdata = BranchData(filename)
    transformerdata = TransformerData(filename)
    busdata_2 = BusData(filename2, config_file)
    branchdata_2 = BranchData(filename2)
    transformerdata_2 = TransformerData(filename2)

    G, edge_labels = calculate_grid(busdata, branchdata, transformerdata, busdata_2)
    create_graph(G, edge_labels)


    mylog.deleteOldLoggers()
    mylog.closeLoggers()
